import asyncio

from loguru import logger

from app.database.session import async_session_maker
from app.services.delivery import (
    claim_next_delivery,
    process_delivery,
)

POLL_INTERVAL = 1


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
