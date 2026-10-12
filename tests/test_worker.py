import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Delivery,
    DeliveryAttempt,
    DeliveryAttemptResult,
    DeliveryStatus,
    FailureType,
)
from app.services.delivery import (
    MAX_DELIVERY_ATTEMPTS,
    claim_next_delivery,
    process_delivery,
)
from app.workers.delivery import recovery_stale_deliveries
from tests.conftest import TestSessionLocal, create_delivery


@pytest.mark.asyncio
async def test_old_processing_delivery_is_recovered(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    assert await recovery_stale_deliveries(db) == 1
    await db.refresh(delivery)
    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_recent_processing_delivery_is_untouched(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    assert await recovery_stale_deliveries(db) == 0
    await db.refresh(delivery)
    assert delivery.status == DeliveryStatus.PROCESSING


@pytest.mark.asyncio
async def test_stale_delivery_with_exhausted_attempts_fails(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    delivery.attempt_count = MAX_DELIVERY_ATTEMPTS

    await recovery_stale_deliveries(db)
    await db.refresh(delivery)
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type == FailureType.RETRIES_EXHAUSTED


async def test_worker_cannot_finish_after_claim_changes_in_another_session(
    db: AsyncSession,
    monkeypatch,
):
    await create_delivery(
        db,
        DeliveryStatus.PENDING,
    )

    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.processing_token is not None

    delivery_id = claimed.id
    old_token = claimed.processing_token
    new_token = uuid.uuid4()

    async def fake_execute_delivery_attempt(destination, message):
        async with TestSessionLocal() as other_db:
            other_delivery = await other_db.get(
                Delivery,
                delivery_id,
            )

            assert other_delivery is not None
            assert other_delivery.processing_token == old_token

            other_delivery.processing_token = new_token
            await other_db.commit()

        return {
            "success": True,
            "external_reference": "telegram-123",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    await process_delivery(
        delivery_id=delivery_id,
        processing_token=old_token,
        db=db,
    )

    async with TestSessionLocal() as verify_db:
        delivery = await verify_db.scalar(
            select(Delivery)
            .options(selectinload(Delivery.attempts))
            .where(Delivery.id == delivery_id)
        )

        assert delivery is not None

        assert delivery.status == DeliveryStatus.PROCESSING
        assert delivery.processing_token == new_token
        assert delivery.delivered_at is None
        assert delivery.external_reference is None

        assert len(delivery.attempts) == 1
        assert delivery.attempts[0].result is None
        assert delivery.attempts[0].finished_at is None


async def test_recovery_closes_abandoned_attempt_as_unknown(
    db: AsyncSession,
):
    await create_delivery(db, DeliveryStatus.PENDING)
    delivery = await claim_next_delivery(db)

    assert delivery is not None
    assert delivery.processing_token is not None

    attempt = DeliveryAttempt(delivery=delivery, trigger=delivery.queued_trigger)
    delivery.attempt_count += 1
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    db.add(attempt)
    await db.commit()

    await recovery_stale_deliveries(db)

    await db.refresh(attempt)
    await db.refresh(delivery)

    assert attempt.result == DeliveryAttemptResult.UNKNOWN
    assert attempt.finished_at is not None

    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.processing_token is None and delivery.processing_started_at is None


async def test_recovered_delivery_gets_new_processing_token(
    db: AsyncSession,
):
    await create_delivery(db, DeliveryStatus.PENDING)
    delivery = await claim_next_delivery(db)

    assert delivery is not None
    assert delivery.processing_token is not None

    old_token = delivery.processing_token
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    await db.commit()

    await recovery_stale_deliveries(db)

    reclaimed = await claim_next_delivery(db)

    assert reclaimed is not None
    assert reclaimed.id == delivery.id
    assert reclaimed.processing_token is not None
    assert reclaimed.processing_token != old_token


async def test_worker_exception_cannot_mutate_after_claim_changes_in_another_session(
    db: AsyncSession,
    monkeypatch,
):
    await create_delivery(db, DeliveryStatus.PENDING)
    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.processing_token is not None

    delivery_id = claimed.id
    old_token = claimed.processing_token
    new_token = uuid.uuid4()

    async def fake_execute_delivery_attempt(destination, message):
        async with TestSessionLocal() as other_db:
            other_delivery = await other_db.get(Delivery, delivery_id)

            assert other_delivery is not None
            assert other_delivery.processing_token == old_token

            other_delivery.processing_token = new_token
            await other_db.commit()

        raise RuntimeError("provider exploded")

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    with pytest.raises(RuntimeError, match="provider exploded"):
        await process_delivery(
            delivery_id=delivery_id,
            processing_token=old_token,
            db=db,
        )

    async with TestSessionLocal() as verify_db:
        delivery = await verify_db.scalar(
            select(Delivery)
            .options(selectinload(Delivery.attempts))
            .where(Delivery.id == delivery_id)
        )

        assert delivery is not None
        assert delivery.status == DeliveryStatus.PROCESSING
        assert delivery.processing_token == new_token
        assert delivery.next_retry_at is None
        assert delivery.last_error is None

        assert len(delivery.attempts) == 1
        assert delivery.attempts[0].result is None
        assert delivery.attempts[0].finished_at is None


async def test_old_worker_cannot_finish_after_recovery_and_reclaim(
    db: AsyncSession,
    monkeypatch,
):
    await create_delivery(db, DeliveryStatus.PENDING)
    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.processing_token is not None

    delivery_id = claimed.id
    old_token = claimed.processing_token
    new_token = None

    async def fake_execute_delivery_attempt(destination, message):
        nonlocal new_token

        async with TestSessionLocal() as other_db:
            stale_delivery = await other_db.get(Delivery, delivery_id)

            assert stale_delivery is not None
            stale_delivery.processing_started_at = datetime.now(
                timezone.utc
            ) - timedelta(minutes=10)
            await other_db.commit()

            assert await recovery_stale_deliveries(other_db) == 1

            reclaimed = await claim_next_delivery(other_db)
            assert reclaimed is not None
            assert reclaimed.id == delivery_id
            assert reclaimed.processing_token is not None

            new_token = reclaimed.processing_token

        return {
            "success": True,
            "external_reference": "stale-worker-result",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    await process_delivery(
        delivery_id=delivery_id,
        processing_token=old_token,
        db=db,
    )

    async with TestSessionLocal() as verify_db:
        delivery = await verify_db.scalar(
            select(Delivery)
            .options(selectinload(Delivery.attempts))
            .where(Delivery.id == delivery_id)
        )

        assert delivery is not None
        assert new_token is not None
        assert new_token != old_token

        assert delivery.status == DeliveryStatus.PROCESSING
        assert delivery.processing_token == new_token
        assert delivery.delivered_at is None
        assert delivery.external_reference is None

        assert len(delivery.attempts) == 1
        assert delivery.attempts[0].result == DeliveryAttemptResult.UNKNOWN
        assert delivery.attempts[0].finished_at is not None


async def test_successful_worker_result_is_durably_persisted(
    db: AsyncSession,
    monkeypatch,
):
    await create_delivery(db, DeliveryStatus.PENDING)
    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.processing_token is not None

    delivery_id = claimed.id
    processing_token = claimed.processing_token

    async def fake_execute_delivery_attempt(destination, message):
        return {
            "success": True,
            "external_reference": "telegram-123",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    await process_delivery(
        delivery_id=delivery_id,
        processing_token=processing_token,
        db=db,
    )

    async with TestSessionLocal() as verify_db:
        delivery = await verify_db.scalar(
            select(Delivery)
            .options(selectinload(Delivery.attempts))
            .where(Delivery.id == delivery_id)
        )

        assert delivery is not None
        assert delivery.status == DeliveryStatus.SUCCEEDED
        assert delivery.processing_token is None
        assert delivery.processing_started_at is None
        assert delivery.delivered_at is not None
        assert delivery.external_reference == "telegram-123"

        assert len(delivery.attempts) == 1
        assert delivery.attempts[0].result == DeliveryAttemptResult.SUCCEEDED
        assert delivery.attempts[0].finished_at is not None
