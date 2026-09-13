import asyncio
import logging

from app.database.session import async_session_maker
from app.services.delivery import (
    claim_next_delivery,
    process_delivery,
)

logger = logging.getLogger(__name__)
POLL_INTERVAL = 1


async def run_delivery_worker() -> None:
    while True:
        try:
            async with async_session_maker() as db:
                delivery = await claim_next_delivery(db)
            if not delivery:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            await process_delivery(delivery_id=delivery.id)

        except Exception as e:
            logger.exception(f"Delivery worker failed: {e}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)
