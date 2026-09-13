import asyncio
import logging

from app.workers.delivery import run_delivery_worker

if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.INFO)
        asyncio.run(run_delivery_worker())
    except KeyboardInterrupt:
        print("\nProcess finished by user...")
