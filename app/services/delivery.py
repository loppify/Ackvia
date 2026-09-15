from datetime import datetime, timedelta, timezone
from operator import and_

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
    Destination,
    FailureType,
    Form,
    Submission,
)
from app.database.session import async_session_maker
from app.services.telegram import format_submission_message, send_telegram_alert

MAX_DELIVERY_ATTEMPTS = 5
RETRY_BASE_DELAY_SECONDS = 30


async def claim_next_delivery(db: AsyncSession) -> Delivery | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Delivery)
        .where(or_(
            Delivery.status == DeliveryStatus.PENDING,
            and_(
                Delivery.status == DeliveryStatus.AWAITING_RETRY,
                Delivery.next_retry_at <= now,
            )
        ))
        .order_by(Delivery.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    delivery = result.scalar_one_or_none()
    if delivery is None:
        await db.rollback()
        return None

    delivery.status = DeliveryStatus.PROCESSING
    delivery.processing_started_at = datetime.now(timezone.utc)
    await db.commit()

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
    delivery_attempt = DeliveryAttempt(delivery=delivery)
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
    else:
        if res.get("failure_type") == "permanent_failure":
            delivery_attempt.result = DeliveryAttemptResult.PERMANENT_FAILURE
            delivery_attempt.error = error

            delivery.status = DeliveryStatus.FAILED
            delivery.failure_type = FailureType.PERMANENT
            delivery.last_error = error
            delivery.next_retry_at = None

        elif res.get("failure_type") == "retryable_failure":
            delivery_attempt.result = DeliveryAttemptResult.RETRYABLE_FAILURE
            delivery_attempt.error = error

            delivery.last_error = error

            if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
                delivery.status = DeliveryStatus.AWAITING_RETRY
                delivery.next_retry_at = now + timedelta(seconds=(RETRY_BASE_DELAY_SECONDS * (2 ** (delivery.attempt_count - 1))))
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.failure_type = FailureType.RETRIES_EXHAUSTED
                delivery.next_retry_at = None

        else:
            delivery_attempt.result = DeliveryAttemptResult.UNKNOWN
            delivery_attempt.error = error

            delivery.status = DeliveryStatus.UNKNOWN
            delivery.last_error = error

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise


def build_submission_message(form: Form, payload: dict) -> str:
    translations = load_translations(form.language)

    def t(key: str) -> str:
        return translations.get(key, key)

    return format_submission_message(form.title, payload, t=t)


async def process_delivery(delivery_id: int) -> None:
    async with async_session_maker() as db:
        delivery = await get_delivery_for_processing(db, delivery_id)

        if delivery is None:
            return

        if delivery.status != DeliveryStatus.PROCESSING:
            return

        attempt = await start_attempt(db, delivery)

        message = build_submission_message(
            delivery.submission.form, delivery.submission.payload
        )

        result = await execute_delivery_attempt(delivery.destination, message)

        await finish_delivery_attempt(db, delivery, attempt, result)
