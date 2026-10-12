from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Delivery,
    DeliveryAttemptResult,
    DeliveryStatus,
    DeliveryTrigger,
)
from app.services.delivery import claim_next_delivery, process_delivery
from tests.conftest import TestSessionLocal


async def test_public_submission_is_processed_and_durably_persisted(
    client,
    db: AsyncSession,
    form_with_destination,
    monkeypatch,
):
    async def fake_execute_delivery_attempt(destination, message):
        return {
            "success": True,
            "external_reference": "telegram-e2e-123",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    response = await client.post(
        f"/f/{form_with_destination.id}",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "Please contact me",
        },
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 202
    submission_id = response.json()["id"]

    delivery = await db.scalar(
        select(Delivery).where(Delivery.submission_id == submission_id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.PENDING

    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.id == delivery.id
    assert claimed.processing_token is not None

    await process_delivery(
        delivery_id=claimed.id,
        processing_token=claimed.processing_token,
        db=db,
    )

    async with TestSessionLocal() as verify_db:
        persisted = await verify_db.scalar(
            select(Delivery)
            .options(
                selectinload(Delivery.submission),
                selectinload(Delivery.attempts),
            )
            .where(Delivery.id == delivery.id)
        )

        assert persisted is not None
        assert persisted.submission.payload == {
            "name": "Alice",
            "email": "alice@example.com",
            "message": "Please contact me",
        }
        assert persisted.status == DeliveryStatus.SUCCEEDED
        assert persisted.delivered_at is not None
        assert persisted.external_reference == "telegram-e2e-123"
        assert persisted.processing_token is None
        assert persisted.processing_started_at is None

        assert len(persisted.attempts) == 1
        assert persisted.attempts[0].trigger == DeliveryTrigger.AUTOMATIC
        assert persisted.attempts[0].result == DeliveryAttemptResult.SUCCEEDED
        assert persisted.attempts[0].finished_at is not None
