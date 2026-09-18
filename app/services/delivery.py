import random
from datetime import datetime, timedelta, timezone
from operator import and_

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import load_translations
from app.database.models import (
    Delivery,
    DeliveryAttempt,
    DeliveryAttemptResult,
    DeliveryStatus,
    DeliveryTrigger,
    Destination,
    FailureType,
    Form,
    Submission,
)
from app.services.telegram import format_submission_message, send_telegram_alert

MAX_DELIVERY_ATTEMPTS = 5
RETRY_BASE_DELAY_SECONDS = 30
RETRY_JITTER_MIN = 0.8
RETRY_JITTER_MAX = 1.2


async def claim_next_delivery(db: AsyncSession) -> Delivery | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Delivery)
        .where(
            or_(
                Delivery.status == DeliveryStatus.PENDING,
                and_(
                    Delivery.status == DeliveryStatus.AWAITING_RETRY,
                    Delivery.next_retry_at <= now,
                ),
            )
        )
        .order_by(Delivery.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    delivery = result.scalar_one_or_none()
    if delivery is None:
        await db.rollback()
        return None
    log = logger.bind(
        delivery_id=delivery.id,
        submission_id=delivery.submission_id,
        destination_id=delivery.destination_id,
    )

    delivery.status = DeliveryStatus.PROCESSING
    delivery.processing_started_at = datetime.now(timezone.utc)
    await db.commit()
    log.info("Delivery claimed")

    return delivery


async def get_delivery_for_processing(
        db: AsyncSession, delivery_id: int
) -> Delivery | None:
    result = await db.execute(
        select(Delivery)
        .where(Delivery.id == delivery_id)
        .options(
            selectinload(Delivery.destination),
            selectinload(Delivery.submission).selectinload(Submission.form),
        )
    )
    return result.scalar_one_or_none()


async def start_attempt(db: AsyncSession, delivery: Delivery):
    delivery_attempt = DeliveryAttempt(
        delivery=delivery, trigger=delivery.queued_trigger
    )
    delivery.attempt_count += 1
    db.add(delivery_attempt)
    await db.commit()
    await db.refresh(delivery_attempt)

    return delivery_attempt


async def execute_delivery_attempt(destination: Destination, message: str):
    res = await send_telegram_alert(int(destination.reference), message)
    return res


async def finish_delivery_attempt(
        db: AsyncSession, delivery: Delivery, delivery_attempt: DeliveryAttempt, res: dict
) -> None:
    log = logger.bind(
        delivery_id=delivery.id,
        submission_id=delivery.submission_id,
        destination_id=delivery.destination_id,
        attempt_count=delivery.attempt_count,
    )
    now = datetime.now(timezone.utc)
    error = res.get("error", "Unknown error")

    delivery_attempt.finished_at = now
    delivery.processing_started_at = None

    if res.get("success", False):
        delivery_attempt.result = DeliveryAttemptResult.SUCCEEDED

        delivery.status = DeliveryStatus.SUCCEEDED
        delivery.delivered_at = now
        delivery.external_reference = res.get("external_reference")
        delivery.failure_type = None
        delivery.last_error = None
        delivery.next_retry_at = None
        log.info("Delivery succeeded")
    else:
        if res.get("failure_type") == "permanent_failure":
            delivery_attempt.result = DeliveryAttemptResult.PERMANENT_FAILURE
            delivery_attempt.error = error

            delivery.status = DeliveryStatus.FAILED
            delivery.failure_type = FailureType.PERMANENT
            delivery.last_error = error
            delivery.next_retry_at = None
            log.bind(error=error).error("Delivery permanently failed")

        elif res.get("failure_type") == "retryable_failure":
            delivery_attempt.result = DeliveryAttemptResult.RETRYABLE_FAILURE
            delivery_attempt.error = error

            delivery.last_error = error

            if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
                delivery.status = DeliveryStatus.AWAITING_RETRY
                delivery.queued_trigger = DeliveryTrigger.RETRY
                delivery.next_retry_at = now + timedelta(
                    seconds=calculate_retry_delay(delivery.attempt_count)
                )

                log.bind(
                    error=delivery_attempt.error, next_retry_at=delivery.next_retry_at
                ).warning("Delivery retry scheduled.")
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.failure_type = FailureType.RETRIES_EXHAUSTED
                delivery.next_retry_at = None
                log.bind(error=delivery_attempt.error).error(
                    "Delivery retries exhausted"
                )

        else:
            delivery_attempt.result = DeliveryAttemptResult.UNKNOWN
            delivery_attempt.error = error

            delivery.status = DeliveryStatus.UNKNOWN
            delivery.last_error = error
            log.info("Delivery result unknown")

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        log.exception("Failed to commit delivery attempt")

        raise


def build_submission_message(form: Form, payload: dict) -> str:
    translations = load_translations(form.language)

    def t(key: str) -> str:
        return translations.get(key, key)

    return format_submission_message(form.title, payload, t=t)


def calculate_retry_delay(attempt_count: int) -> float:
    base_delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt_count - 1))
    return base_delay * random.uniform(
        RETRY_JITTER_MIN,
        RETRY_JITTER_MAX,
    )


async def process_delivery(delivery_id: int, db: AsyncSession) -> None:
    log = logger.bind(delivery_id=delivery_id)
    delivery = None
    attempt = None

    try:
        delivery = await get_delivery_for_processing(db, delivery_id)

        if delivery is None:
            log.warning("Delivery not found")
            return

        if delivery.status != DeliveryStatus.PROCESSING:
            log.bind(status=delivery.status).warning(
                "Delivery is not in processing state"
            )
            return

        attempt = await start_attempt(db, delivery)

        message = build_submission_message(
            delivery.submission.form,
            delivery.submission.payload,
        )

        result = await execute_delivery_attempt(
            delivery.destination,
            message,
        )

        await finish_delivery_attempt(
            db,
            delivery,
            attempt,
            result,
        )

    except Exception as exc:
        log.exception("Unexpected error while processing delivery")

        delivery_db_id = delivery.id if delivery is not None else None
        attempt_id = attempt.id if attempt is not None else None

        await db.rollback()

        if delivery_db_id is None:
            raise

        delivery = await get_delivery_for_processing(db, delivery_id)

        if delivery is None:
            raise

        if attempt_id is not None:
            attempt = await db.get(DeliveryAttempt, attempt_id)

        now = datetime.now(timezone.utc)
        error = str(exc)
        delivery.processing_started_at = None
        delivery.last_error = error

        if attempt is not None:
            attempt.finished_at = now
            attempt.result = DeliveryAttemptResult.UNKNOWN
            attempt.error = error

        if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
            delivery.status = DeliveryStatus.AWAITING_RETRY
            delivery.queued_trigger = DeliveryTrigger.RETRY
            delivery.failure_type = None
            delay = calculate_retry_delay(delivery.attempt_count)
            delivery.next_retry_at = now + timedelta(seconds=delay)
            log.bind(
                attempt_count=delivery.attempt_count,
                next_retry_at=delivery.next_retry_at,
            ).warning("Delivery recovered and retry scheduled")

        else:
            delivery.status = DeliveryStatus.FAILED
            delivery.failure_type = FailureType.RETRIES_EXHAUSTED
            delivery.next_retry_at = None

            log.bind(
                attempt_count=delivery.attempt_count,
            ).error("Delivery failed after retries exhausted")

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to persist delivery recovery")
            raise
        raise

class DeliveryNotFoundError(Exception):
    ...

class DeliveryNotReplayableError(Exception):
    ...

async def manual_delivery(delivery_id, db: AsyncSession):
    delivery = await db.get(Delivery, delivery_id)

    if delivery is None:
        raise DeliveryNotFoundError
    if delivery.status not in (
            DeliveryStatus.FAILED,
            DeliveryStatus.UNKNOWN,
    ):
        raise DeliveryNotReplayableError

    delivery.status = DeliveryStatus.PENDING
    delivery.queued_trigger = DeliveryTrigger.MANUAL_REPLAY
    delivery.failure_type = None
    delivery.next_retry_at = None
    delivery.processing_started_at = None
    await db.commit()
    await db.refresh(delivery)
    return delivery
