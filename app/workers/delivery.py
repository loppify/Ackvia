import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Delivery, DeliveryStatus, FailureType
from app.database.session import async_session_maker
from app.services.delivery import (
    MAX_DELIVERY_ATTEMPTS,
    claim_next_delivery,
    process_delivery,
)

POLL_INTERVAL = 1
PROCESSING_TIMEOUT_SECONDS = 300


async def run_delivery_worker() -> None:
    logger.info("Delivery worker")
    while True:
        try:
            async with async_session_maker() as db:
                delivery = await claim_next_delivery(db)
            if not delivery:
                logger.debug("No deliveries available")
                await asyncio.sleep(POLL_INTERVAL)
                continue
            async with async_session_maker() as db:
                await process_delivery(delivery_id=delivery.id, db=db)

        except Exception as e:
            logger.warning("Delivery worker failed: {}", e)
            await asyncio.sleep(POLL_INTERVAL)


async def recovery_stale_deliveries(db: AsyncSession) -> int:
    log = logger
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)

    result = await db.scalars(
        select(Delivery).where(
            Delivery.status == DeliveryStatus.PROCESSING,
            Delivery.processing_started_at <= cutoff,
        )
    )
    stale_deliveries = result.all()
    for delivery in stale_deliveries:
        log.bind(
            processing_started_at=delivery.processing_started_at,
        ).warning("Recovering stale delivery")

        if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
            delivery.status = DeliveryStatus.AWAITING_RETRY
            delivery.processing_started_at = None
            delivery.next_retry_at = now
        elif delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            delivery.status = DeliveryStatus.FAILED
            delivery.failure_type = FailureType.RETRIES_EXHAUSTED
            delivery.processing_started_at = None
            delivery.next_retry_at = None
    return len(stale_deliveries)
