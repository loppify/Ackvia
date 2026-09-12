from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Delivery,
    DeliveryAttempt,
    DeliveryAttemptResult,
    DeliveryStatus,
    Destination,
    FailureType,
)
from app.services.telegram import send_telegram_alert


async def attempt_delivery(
    db: AsyncSession,
    delivery: Delivery,
    destination: Destination,
    message: str,
) -> None:
    delivery_attempt = DeliveryAttempt(delivery=delivery)
    delivery.attempt_count = delivery.attempt_count + 1
    db.add(delivery_attempt)

    res = await send_telegram_alert(int(destination.reference), message)
    if res.get("success", False):
        delivery_attempt.result = DeliveryAttemptResult.SUCCEEDED
        delivery.status = DeliveryStatus.SUCCEEDED
    else:
        delivery_attempt.result = DeliveryAttemptResult.PERMANENT_FAILURE
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_type = FailureType.PERMANENT
        delivery_attempt.error = res.get("error", "Unknown error")
        delivery.last_error = res.get("error", "Unknown error")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
