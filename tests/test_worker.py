from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DeliveryStatus, FailureType
from app.services.delivery import MAX_DELIVERY_ATTEMPTS
from app.workers.delivery import recovery_stale_deliveries
from tests.conftest import create_delivery


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
