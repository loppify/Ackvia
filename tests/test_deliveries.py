from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.services.delivery import (
    MAX_DELIVERY_ATTEMPTS,
    claim_next_delivery,
    finish_delivery_attempt,
    process_delivery,
)
from app.workers.delivery import recovery_stale_deliveries
from tests.conftest import create_delivery, create_form


@pytest.mark.asyncio
async def test_delivery_creation(db: AsyncSession):
    form = await create_form(
        db,
        title="Landing Test",
        language="en",
    )

    destination = Destination(
        form=form,
        type="telegram",
        reference="987654321",
    )

    submission = Submission(
        form=form,
        payload={"name": "Ivan"},
    )

    Delivery(
        submission=submission,
        destination=destination,
    )

    db.add(form)
    await db.commit()

    stored_form = await db.scalar(select(Form).order_by(Form.id))
    stored_destination = await db.scalar(select(Destination).order_by(Destination.id))
    stored_submission = await db.scalar(select(Submission).order_by(Submission.id))
    stored_delivery = await db.scalar(select(Delivery).order_by(Delivery.id))

    assert stored_form is not None
    assert stored_destination is not None
    assert stored_submission is not None
    assert stored_delivery is not None

    assert stored_form.title == "Landing Test"
    assert stored_destination.type == "telegram"
    assert stored_submission.payload == {"name": "Ivan"}
    assert stored_delivery.status == DeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_new_delivery_starts_pending_without_attempts(
        db: AsyncSession,
):
    form = await create_form(
        db,
        title="Landing Test",
        language="en",
    )

    destination = Destination(
        form=form,
        type="telegram",
        reference="987654321",
    )

    submission = Submission(
        form=form,
        payload={"name": "Ivan"},
    )

    Delivery(
        submission=submission,
        destination=destination,
    )

    db.add(form)
    await db.commit()

    result = await db.execute(select(Delivery).options(selectinload(Delivery.attempts)))
    delivery = result.scalar_one()

    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempt_count == 0
    assert delivery.attempts == []


@pytest.mark.asyncio
async def test_duplicate_delivery_failure(db: AsyncSession):
    form = await create_form(
        db,
        title="Landing Test",
        language="en",
    )

    destination = Destination(
        form=form,
        type="telegram",
        reference="987654321",
    )

    submission = Submission(
        form=form,
        payload={"name": "Ivan"},
    )

    Delivery(
        submission=submission,
        destination=destination,
    )
    Delivery(
        submission=submission,
        destination=destination,
    )

    db.add(form)

    with pytest.raises(IntegrityError):
        await db.commit()

    await db.rollback()

    forms = (await db.scalars(select(Form))).all()
    submissions = (await db.scalars(select(Submission))).all()
    deliveries = (await db.scalars(select(Delivery))).all()

    assert forms == []
    assert submissions == []
    assert deliveries == []


@pytest.mark.asyncio
async def test_delivery_states_are_independent(
        db: AsyncSession,
):
    form = await create_form(
        db,
        title="Landing Test",
        language="en",
    )

    destination_a = Destination(
        form=form,
        type="telegram",
        reference="111111111",
    )
    destination_b = Destination(
        form=form,
        type="telegram",
        reference="222222222",
    )
    destination_c = Destination(
        form=form,
        type="telegram",
        reference="333333333",
    )

    submission = Submission(
        form=form,
        payload={"name": "Ivan"},
    )

    delivery_a = Delivery(
        submission=submission,
        destination=destination_a,
    )
    delivery_b = Delivery(
        submission=submission,
        destination=destination_b,
    )
    delivery_c = Delivery(
        submission=submission,
        destination=destination_c,
    )

    db.add(form)
    await db.commit()

    delivery_a.status = DeliveryStatus.SUCCEEDED

    delivery_b.status = DeliveryStatus.FAILED
    delivery_b.failure_type = FailureType.PERMANENT

    delivery_c.status = DeliveryStatus.PENDING

    await db.commit()

    result = await db.execute(
        select(Delivery).where(Delivery.submission_id == submission.id)
    )
    deliveries = result.scalars().all()

    assert len(deliveries) == 3

    statuses = {delivery.status for delivery in deliveries}

    assert statuses == {
        DeliveryStatus.SUCCEEDED,
        DeliveryStatus.FAILED,
        DeliveryStatus.PENDING,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        DeliveryStatus.PENDING,
        DeliveryStatus.SUCCEEDED,
        DeliveryStatus.FAILED,
        DeliveryStatus.AWAITING_RETRY,
        DeliveryStatus.UNKNOWN,
    ],
)
async def test_delivery_status_is_persisted(
        db: AsyncSession,
        status: DeliveryStatus,
):
    delivery = await create_delivery(
        db,
        status=status,
    )

    result = await db.execute(select(Delivery).where(Delivery.id == delivery.id))
    stored_delivery = result.scalar_one()

    assert stored_delivery.status == status


@pytest.mark.asyncio
async def test_awaiting_retry_delivery_can_be_selected_when_due(
        db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.AWAITING_RETRY,
    )

    delivery.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Delivery).where(
            Delivery.status == DeliveryStatus.AWAITING_RETRY,
            Delivery.next_retry_at <= now,
        )
    )
    selected_delivery = result.scalar_one()

    assert selected_delivery.id == delivery.id


@pytest.mark.asyncio
async def test_awaiting_retry_delivery_is_not_selected_before_due(
        db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.AWAITING_RETRY,
    )

    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Delivery).where(
            Delivery.status == DeliveryStatus.AWAITING_RETRY,
            Delivery.next_retry_at <= now,
        )
    )
    selected_delivery = result.scalar_one_or_none()

    assert selected_delivery is None


@pytest.mark.asyncio
async def test_retryable_failure_schedules_retry(
        db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        DeliveryStatus.PROCESSING,
    )
    delivery.attempt_count = 1
    delivery.processing_started_at = datetime.now(timezone.utc)

    attempt = DeliveryAttempt(delivery=delivery, trigger=delivery.queued_trigger)
    db.add(attempt)
    await db.commit()

    before = datetime.now(timezone.utc)

    await finish_delivery_attempt(
        db,
        delivery,
        attempt,
        {
            "success": False,
            "failure_type": "retryable_failure",
            "error": "Telegram temporarily unavailable",
        },
    )

    after = datetime.now(timezone.utc)

    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.failure_type is None
    assert delivery.last_error == "Telegram temporarily unavailable"
    assert attempt.result == DeliveryAttemptResult.RETRYABLE_FAILURE
    assert attempt.error == "Telegram temporarily unavailable"
    assert attempt.finished_at is not None
    assert delivery.next_retry_at is not None
    assert before + timedelta(seconds=24) <= delivery.next_retry_at
    assert delivery.next_retry_at <= after + timedelta(seconds=36)
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_retry_delay_increases_with_attempt_count(
        db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        DeliveryStatus.PROCESSING,
    )
    delivery.attempt_count = 3

    attempt = DeliveryAttempt(delivery=delivery, trigger=delivery.queued_trigger)
    db.add(attempt)
    await db.commit()

    datetime.now(timezone.utc)

    await finish_delivery_attempt(
        db,
        delivery,
        attempt,
        {
            "success": False,
            "failure_type": "retryable_failure",
            "error": "Temporary failure",
        },
    )

    after = datetime.now(timezone.utc)

    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.next_retry_at is not None

    assert after + timedelta(seconds=96) <= delivery.next_retry_at
    assert delivery.next_retry_at <= after + timedelta(seconds=144)


@pytest.mark.asyncio
async def test_retryable_failure_exhausts_retries(
        db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        DeliveryStatus.PROCESSING,
    )
    delivery.attempt_count = 5
    delivery.next_retry_at = datetime.now(timezone.utc)

    attempt = DeliveryAttempt(delivery=delivery, trigger=delivery.queued_trigger)
    db.add(attempt)
    await db.commit()

    await finish_delivery_attempt(
        db,
        delivery,
        attempt,
        {
            "success": False,
            "failure_type": "retryable_failure",
            "error": "Still unavailable",
        },
    )

    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type == FailureType.RETRIES_EXHAUSTED
    assert delivery.last_error == "Still unavailable"
    assert delivery.processing_started_at is None

    assert attempt.result == DeliveryAttemptResult.RETRYABLE_FAILURE
    assert attempt.error == "Still unavailable"
    assert attempt.finished_at is not None
    assert delivery.next_retry_at is None


@pytest.mark.asyncio
async def test_unexpected_exception_schedules_retry(db: AsyncSession, monkeypatch):
    async def fake_execute_delivery_attempt(destination, message):
        raise RuntimeError("Test Failure")

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt", fake_execute_delivery_attempt
    )
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)

    with pytest.raises(RuntimeError):
        await process_delivery(delivery.id, db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.attempts[-1].result == DeliveryAttemptResult.UNKNOWN
    assert delivery.attempts[-1].finished_at is not None
    assert delivery.next_retry_at is not None
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_unexpected_exception_respects_max_attempts(
        db: AsyncSession, monkeypatch
):
    async def fake_execute_delivery_attempt(destination, message):
        raise RuntimeError("Test Failure")

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt", fake_execute_delivery_attempt
    )
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.attempt_count = MAX_DELIVERY_ATTEMPTS - 1

    with pytest.raises(RuntimeError):
        await process_delivery(delivery.id, db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type == FailureType.RETRIES_EXHAUSTED
    assert delivery.attempts[-1].result == DeliveryAttemptResult.UNKNOWN
    assert delivery.next_retry_at is None and delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_successful_processing_still_works(db: AsyncSession, monkeypatch):
    async def fake_execute_delivery_attempt(destination, message):
        return {"success": True, "external_reference": str(12334567)}

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt", fake_execute_delivery_attempt
    )
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.attempt_count = MAX_DELIVERY_ATTEMPTS - 1

    await process_delivery(delivery.id, db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )
    assert delivery is not None
    assert delivery.status == DeliveryStatus.SUCCEEDED
    assert delivery.attempts[-1].result == DeliveryAttemptResult.SUCCEEDED
    assert delivery.delivered_at is not None
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_permanent_failre_still_works(db: AsyncSession, monkeypatch):
    async def fake_execute_delivery_attempt(destination, message):
        return {
            "success": False,
            "error": "Chat not found",
            "failure_type": "permanent_failure",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt", fake_execute_delivery_attempt
    )
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)

    await process_delivery(delivery.id, db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type == FailureType.PERMANENT
    assert delivery.attempts[-1].result == DeliveryAttemptResult.PERMANENT_FAILURE
    assert delivery.next_retry_at is None


@pytest.mark.asyncio
async def test_old_processing_delivery_is_recovered(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    recovery_amount = await recovery_stale_deliveries(db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.next_retry_at is not None
    assert delivery.processing_started_at is None
    assert recovery_amount == 1


@pytest.mark.asyncio
async def test_recent_processing_delivery_is_untouched(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    recovery_amount = await recovery_stale_deliveries(db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.PROCESSING
    assert recovery_amount == 0


@pytest.mark.asyncio
async def test_non_processing_deliveries_are_untouched(db: AsyncSession):
    deliveries = [
        await create_delivery(db, DeliveryStatus.SUCCEEDED),
        await create_delivery(db, DeliveryStatus.FAILED),
        await create_delivery(db, DeliveryStatus.AWAITING_RETRY),
    ]
    for delivery in deliveries:
        delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(
            minutes=10
        )

    expected_statuses = {delivery.id: delivery.status for delivery in deliveries}
    recovery_amount = await recovery_stale_deliveries(db)

    deliveries = await db.scalars(
        select(Delivery).options(selectinload(Delivery.attempts))
    )
    for delivery in deliveries.all():
        assert delivery is not None
        assert delivery.status == expected_statuses[delivery.id]

    assert recovery_amount == 0


@pytest.mark.asyncio
async def test_stale_delivery_with_exhausted_attempts_fails(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    delivery.attempt_count = MAX_DELIVERY_ATTEMPTS

    await recovery_stale_deliveries(db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type == FailureType.RETRIES_EXHAUSTED
    assert delivery.next_retry_at is None
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_recovered_delivery_can_be_claimed(db: AsyncSession):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    await recovery_stale_deliveries(db)

    delivery = await db.scalar(
        select(Delivery)
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery.id)
    )

    assert delivery is not None
    assert delivery.status == DeliveryStatus.AWAITING_RETRY
    assert delivery.next_retry_at is not None
    assert delivery.processing_started_at is None

    delivery = await claim_next_delivery(db)

    assert delivery is not None
    assert delivery.status == DeliveryStatus.PROCESSING
    assert delivery.processing_started_at is not None


@pytest.mark.asyncio
async def test_get_delivery_returns_delivery(db: AsyncSession, client):
    delivery = await create_delivery(db)
    response = await client.get(f"/api/deliveries/{delivery.id}")

    assert response.status_code == 200
    assert response.json()["id"] == delivery.id
    assert response.json()["attempts"] == []


@pytest.mark.asyncio
async def test_get_delivery_returns_attempts(db: AsyncSession, client):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)
    attempt = DeliveryAttempt(
        delivery=delivery,
        result=DeliveryAttemptResult.RETRYABLE_FAILURE,
        error="Telegram unavailable",
        trigger=DeliveryTrigger.AUTOMATIC,
        finished_at=datetime.now(timezone.utc),
    )
    delivery.attempt_count = 1
    db.add(attempt)
    await db.commit()

    response = await client.get(f"/api/deliveries/{delivery.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["attempt_count"] == 1
    assert (
        data["attempts"][0]["result"]
        == DeliveryAttemptResult.RETRYABLE_FAILURE.value
    )


@pytest.mark.asyncio
async def test_get_delivery_returns_404_when_not_found(client):
    response = await client.get("/api/deliveries/999999")
    assert response.status_code == 404
