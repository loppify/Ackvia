from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    DeliveryAttempt,
    DeliveryAttemptResult,
    DeliveryStatus,
    DeliveryTrigger,
)
from app.services.delivery import (
    DeliveryNotFoundError,
    DeliveryNotReplayableError,
    claim_next_delivery,
    manual_delivery,
    process_delivery,
)
from tests.conftest import create_delivery


@pytest.mark.asyncio
async def test_failed_delivery_can_be_queued_for_manual_replay(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.FAILED)
    delivery.attempt_count = 5
    delivery.next_retry_at = datetime.now(timezone.utc)
    await db.commit()

    result = await manual_delivery(delivery.id, db)
    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert result.failure_type is None
    assert result.attempt_count == 5


@pytest.mark.asyncio
async def test_unknown_delivery_can_be_queued_for_manual_replay(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.UNKNOWN)
    result = await manual_delivery(delivery.id, db)
    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY


@pytest.mark.asyncio
async def test_manual_replay_raises_not_found_for_missing_delivery(db: AsyncSession):
    with pytest.raises(DeliveryNotFoundError):
        await manual_delivery(999999, db)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [
    DeliveryStatus.PENDING,
    DeliveryStatus.PROCESSING,
    DeliveryStatus.AWAITING_RETRY,
    DeliveryStatus.SUCCEEDED,
])
async def test_manual_replay_rejects_non_replayable_status(db, status):
    delivery = await create_delivery(db, status)
    with pytest.raises(DeliveryNotReplayableError):
        await manual_delivery(delivery.id, db)


@pytest.mark.asyncio
async def test_replay_failed_delivery_endpoint(client, db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.FAILED)
    response = await client.post(f"/api/deliveries/{delivery.id}/replay")
    assert response.status_code == 202
    assert response.json()["status"] == DeliveryStatus.PENDING.value


@pytest.mark.asyncio
async def test_replay_missing_delivery_returns_404(client):
    response = await client.post("/api/deliveries/999999/replay")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manual_replay_is_recorded_in_attempt_history(
        client, db: AsyncSession, monkeypatch,
):
    delivery = await create_delivery(db, DeliveryStatus.FAILED)
    response = await client.post(f"/api/deliveries/{delivery.id}/replay")
    assert response.status_code == 202

    db.expire_all()
    claimed = await claim_next_delivery(db)
    assert claimed.queued_trigger == DeliveryTrigger.MANUAL_REPLAY

    async def fake_execute_delivery_attempt(destination, message):
        return {"success": True, "external_reference": "manual-replay-test"}

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )
    await process_delivery(delivery.id, db)

    result = await db.scalars(
        select(DeliveryAttempt).where(DeliveryAttempt.delivery_id == delivery.id)
    )
    attempt = result.one()
    assert attempt.trigger == DeliveryTrigger.MANUAL_REPLAY
    assert attempt.result == DeliveryAttemptResult.SUCCEEDED
