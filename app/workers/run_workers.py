import asyncio

from loguru import logger

from app.workers.delivery import run_delivery_worker

if __name__ == "__main__":
    try:
        logger.info("Starting delivery worker...")
        asyncio.run(run_delivery_worker())
    except KeyboardInterrupt:
        logger.info("\nWorker stopped by user...")
