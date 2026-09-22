from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DeliveryStatus
from tests.conftest import create_delivery


@pytest.mark.asyncio
async def test_get_submission_returns_submission_with_payload(
        db: AsyncSession,
        client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PENDING)
    submission = delivery.submission

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == submission.id
    assert data["payload"] == {"email": "test@example.com"}
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_submission_returns_deliveries(
        db: AsyncSession,
        client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PENDING)
    submission = delivery.submission

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 200

    data = response.json()

    assert len(data["deliveries"]) == 1

    stored_delivery = data["deliveries"][0]

    assert stored_delivery["id"] == delivery.id
    assert stored_delivery["destination_id"] == delivery.destination_id
    assert stored_delivery["status"] == DeliveryStatus.PENDING.value
    assert stored_delivery["attempt_count"] == 0


@pytest.mark.asyncio
async def test_get_submission_returns_delivery_state(
        db: AsyncSession,
        client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.AWAITING_RETRY)

    delivery.attempt_count = 2
    delivery.last_error = "Telegram unavailable"
    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)

    await db.commit()

    response = await client.get(f"/api/submissions/{delivery.submission_id}")

    assert response.status_code == 200

    data = response.json()
    stored_delivery = data["deliveries"][0]

    assert stored_delivery["status"] == DeliveryStatus.AWAITING_RETRY.value
    assert stored_delivery["attempt_count"] == 2
    assert stored_delivery["last_error"] == "Telegram unavailable"
    assert stored_delivery["next_retry_at"] is not None
    assert stored_delivery["delivered_at"] is None


@pytest.mark.asyncio
async def test_get_submission_not_found(
        client: AsyncClient,
):
    response = await client.get("/api/submissions/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_submission_invalid_id(
        client: AsyncClient,
):
    response = await client.get("/api/submissions/not-an-id")

    assert response.status_code == 422
