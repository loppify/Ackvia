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
RECOVERY_INTERVAL_SECONDS = 60


async def run_delivery_worker() -> None:
    logger.info("Delivery worker")

    last_recovery_at: datetime | None = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            if last_recovery_at is None or now - last_recovery_at >= timedelta(
                seconds=RECOVERY_INTERVAL_SECONDS
            ):
                async with async_session_maker() as db:
                    recovered = await recovery_stale_deliveries(db)
                if recovered:
                    logger.warning("Recovered {} stale deliveries", recovered)

                last_recovery_at = now

            async with async_session_maker() as db:
                delivery = await claim_next_delivery(db)
            if delivery is None:
                logger.debug("No deliveries available")
                await asyncio.sleep(POLL_INTERVAL)
                continue
            async with async_session_maker() as db:
                await process_delivery(delivery_id=delivery.id, db=db)

        except Exception:
            logger.exception("Delivery worker iteration failed")
            await asyncio.sleep(POLL_INTERVAL)


async def recovery_stale_deliveries(db: AsyncSession) -> int:
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
        log = logger.bind(
            delivery_id=delivery.id,
            attempt_count=delivery.attempt_count,
            processing_started_at=delivery.processing_started_at,
        )
        log.warning("Recovering stale delivery")

        if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
            delivery.status = DeliveryStatus.AWAITING_RETRY
            delivery.processing_started_at = None
            delivery.next_retry_at = now
            log.warning("Stale delivery scheduled for retry")

        elif delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            delivery.status = DeliveryStatus.FAILED
            delivery.failure_type = FailureType.RETRIES_EXHAUSTED
            delivery.processing_started_at = None
            delivery.next_retry_at = None
            log.error("Stale delivery retries exhausted")

    if stale_deliveries:
        await db.commit()
    return len(stale_deliveries)
