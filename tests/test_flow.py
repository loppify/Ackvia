import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.database.models import (
    Base,
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
from app.database.session import get_db
from app.main import app
from app.services.delivery import (
    MAX_DELIVERY_ATTEMPTS,
    DeliveryNotFoundError,
    DeliveryNotReplayableError,
    claim_next_delivery,
    finish_delivery_attempt,
    manual_delivery,
    process_delivery,
)
from app.workers.delivery import recovery_stale_deliveries

load_dotenv(".env.test")

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

assert TEST_DATABASE_URL is not None
assert "test" in TEST_DATABASE_URL

engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def create_delivery(
    db: AsyncSession,
    status: DeliveryStatus = DeliveryStatus.PENDING,
) -> Delivery:
    form = Form(
        title="Test form",
        language="en",
    )

    destination = Destination(
        form=form,
        type="telegram",
        reference="123456789",
    )

    submission = Submission(
        form=form,
        payload={"email": "test@example.com"},
    )

    delivery = Delivery(
        submission=submission,
        destination=destination,
        status=status,
        failure_type=(
            FailureType.PERMANENT if status == DeliveryStatus.FAILED else None
        ),
        queued_trigger=DeliveryTrigger.AUTOMATIC,
    )

    db.add(form)
    await db.commit()

    return delivery


# ---------------------------------------------------------------------------
# Form API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_form_uuid(client: AsyncClient):
    random_id = uuid.uuid4()

    response = await client.post(
        f"/f/{random_id}",
        json={"dummy": "data"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delivery creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_creation(db: AsyncSession):
    form = Form(
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
    form = Form(
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
    form = Form(
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


# ---------------------------------------------------------------------------
# Delivery states
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_states_are_independent(
    db: AsyncSession,
):
    form = Form(
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


# ---------------------------------------------------------------------------
# Retry selection
# ---------------------------------------------------------------------------


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
async def test_get_form_submissions_returns_only_its_submissions(
    db: AsyncSession,
    client: AsyncClient,
):
    form = Form(title="Test form")

    submission_1 = Submission(
        form=form,
        payload={"name": "Ivan"},
    )
    submission_2 = Submission(
        form=form,
        payload={"name": "Petro"},
    )

    db.add(form)
    await db.commit()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        submission_1.id,
        submission_2.id,
    }


@pytest.mark.asyncio
async def test_get_form_submissions_does_not_return_other_form_submissions(
    db: AsyncSession,
    client: AsyncClient,
):
    form_1 = Form(title="Form 1")
    form_2 = Form(title="Form 2")

    submission_1 = Submission(
        form=form_1,
        payload={"name": "Ivan"},
    )
    submission_2 = Submission(
        form=form_2,
        payload={"name": "Petro"},
    )

    db.add_all([form_1, form_2])
    await db.commit()

    response = await client.get(f"/api/forms/{form_1.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == submission_1.id
    assert data[0]["id"] != submission_2.id


@pytest.mark.asyncio
async def test_get_form_submissions_are_ordered_newest_first(
    db: AsyncSession,
    client: AsyncClient,
):
    form = Form(title="Test form")

    old_submission = Submission(
        form=form,
        payload={"name": "Old"},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    new_submission = Submission(
        form=form,
        payload={"name": "New"},
        created_at=datetime.now(timezone.utc),
    )

    db.add(form)
    await db.commit()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == new_submission.id
    assert data[1]["id"] == old_submission.id


@pytest.mark.asyncio
async def test_get_form_submissions_respects_limit(
    db: AsyncSession,
    client: AsyncClient,
):
    form = Form(title="Test form")

    for i in range(5):
        Submission(
            form=form,
            payload={"number": i},
        )

    db.add(form)
    await db.commit()

    response = await client.get(
        f"/api/forms/{form.id}/submissions",
        params={"limit": 2},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_form_submissions_respects_offset(
    db: AsyncSession,
    client: AsyncClient,
):
    form = Form(title="Test form")

    now = datetime.now(timezone.utc)

    submissions = [
        Submission(
            form=form,
            payload={"number": i},
            created_at=now + timedelta(seconds=i),
        )
        for i in range(5)
    ]

    db.add(form)
    await db.commit()

    response = await client.get(
        f"/api/forms/{form.id}/submissions",
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == submissions[2].id
    assert data[1]["id"] == submissions[1].id


@pytest.mark.asyncio
async def test_get_form_submissions_returns_404_for_unknown_form(
    client: AsyncClient,
):
    form_id = uuid.uuid4()

    response = await client.get(f"/api/forms/{form_id}/submissions")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_submission_returns_submission_with_payload(
    db: AsyncSession,
    client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PENDING)
    submission = delivery.submission

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == submission.id
    assert data["payload"] == {"email": "test@example.com"}
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_submission_returns_deliveries(
    db: AsyncSession,
    client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PENDING)
    submission = delivery.submission

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 200

    data = response.json()

    assert len(data["deliveries"]) == 1

    stored_delivery = data["deliveries"][0]

    assert stored_delivery["id"] == delivery.id
    assert stored_delivery["destination_id"] == delivery.destination_id
    assert stored_delivery["status"] == DeliveryStatus.PENDING.value
    assert stored_delivery["attempt_count"] == 0


@pytest.mark.asyncio
async def test_get_submission_returns_delivery_state(
    db: AsyncSession,
    client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.AWAITING_RETRY)

    delivery.attempt_count = 2
    delivery.last_error = "Telegram unavailable"
    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)

    await db.commit()

    response = await client.get(f"/api/submissions/{delivery.submission_id}")

    assert response.status_code == 200

    data = response.json()
    stored_delivery = data["deliveries"][0]

    assert stored_delivery["status"] == DeliveryStatus.AWAITING_RETRY.value
    assert stored_delivery["attempt_count"] == 2
    assert stored_delivery["last_error"] == "Telegram unavailable"
    assert stored_delivery["next_retry_at"] is not None
    assert stored_delivery["delivered_at"] is None


@pytest.mark.asyncio
async def test_get_submission_not_found(
    client: AsyncClient,
):
    response = await client.get("/api/submissions/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_submission_invalid_id(
    client: AsyncClient,
):
    response = await client.get("/api/submissions/not-an-id")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_forms_returns_forms(
    db: AsyncSession,
    client: AsyncClient,
):
    form_1 = Form(title="Form 1")
    form_2 = Form(title="Form 2")

    db.add_all([form_1, form_2])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        str(form_1.id),
        str(form_2.id),
    }


@pytest.mark.asyncio
async def test_get_forms_are_ordered_newest_first(
    db: AsyncSession,
    client: AsyncClient,
):
    now = datetime.now(timezone.utc)

    old_form = Form(
        title="Old form",
        created_at=now - timedelta(hours=1),
    )
    new_form = Form(
        title="New form",
        created_at=now,
    )

    db.add_all([old_form, new_form])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(new_form.id)
    assert data[1]["id"] == str(old_form.id)


@pytest.mark.asyncio
async def test_get_forms_respects_limit_and_offset(
    db: AsyncSession,
    client: AsyncClient,
):
    now = datetime.now(timezone.utc)

    forms = [
        Form(
            title=f"Form {i}",
            created_at=now + timedelta(seconds=i),
        )
        for i in range(5)
    ]

    db.add_all(forms)
    await db.commit()

    response = await client.get(
        "/api/forms",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(forms[3].id)
    assert data[1]["id"] == str(forms[2].id)


@pytest.mark.asyncio
async def test_get_forms_returns_empty_list_when_no_forms_exist(
    client: AsyncClient,
):
    response = await client.get("/api/forms")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_delivery_returns_delivery(
    db: AsyncSession,
    client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PENDING)

    response = await client.get(f"/api/deliveries/{delivery.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == delivery.id
    assert data["submission_id"] == delivery.submission_id
    assert data["destination_id"] == delivery.destination_id
    assert data["status"] == DeliveryStatus.PENDING.value
    assert data["attempt_count"] == 0
    assert data["attempts"] == []


@pytest.mark.asyncio
async def test_get_delivery_returns_attempts(
    db: AsyncSession,
    client: AsyncClient,
):
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

    assert response.status_code == 200

    data = response.json()

    assert data["attempt_count"] == 1
    assert len(data["attempts"]) == 1

    stored_attempt = data["attempts"][0]

    assert stored_attempt["id"] == attempt.id
    assert stored_attempt["result"] == DeliveryAttemptResult.RETRYABLE_FAILURE.value
    assert stored_attempt["error"] == "Telegram unavailable"
    assert stored_attempt["trigger"] == DeliveryTrigger.AUTOMATIC.value
    assert stored_attempt["finished_at"] is not None


@pytest.mark.asyncio
async def test_get_delivery_returns_attempts_in_chronological_order(
    db: AsyncSession,
    client: AsyncClient,
):
    delivery = await create_delivery(db, DeliveryStatus.PROCESSING)

    now = datetime.now(timezone.utc)

    first_attempt = DeliveryAttempt(
        delivery=delivery,
        trigger=DeliveryTrigger.AUTOMATIC,
        created_at=now - timedelta(minutes=2),
    )

    second_attempt = DeliveryAttempt(
        delivery=delivery,
        trigger=DeliveryTrigger.RETRY,
        created_at=now - timedelta(minutes=1),
    )

    db.add_all([first_attempt, second_attempt])
    await db.commit()

    response = await client.get(f"/api/deliveries/{delivery.id}")

    assert response.status_code == 200

    attempts = response.json()["attempts"]

    assert len(attempts) == 2
    assert attempts[0]["id"] == first_attempt.id
    assert attempts[1]["id"] == second_attempt.id


@pytest.mark.asyncio
async def test_get_delivery_returns_404_when_not_found(
    client: AsyncClient,
):
    response = await client.get("/api/deliveries/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_failed_delivery_can_be_queued_for_manual_replay(
    db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.FAILED,
    )
    delivery.attempt_count = 5
    delivery.next_retry_at = datetime.now(timezone.utc)
    delivery.processing_started_at = datetime.now(timezone.utc)
    await db.commit()

    result = await manual_delivery(delivery.id, db)

    assert result is not None
    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert result.failure_type is None
    assert result.next_retry_at is None
    assert result.processing_started_at is None
    assert result.attempt_count == 5


@pytest.mark.asyncio
async def test_unknown_delivery_can_be_queued_for_manual_replay(
    db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.UNKNOWN,
    )

    result = await manual_delivery(delivery.id, db)

    assert result is not None
    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert result.failure_type is None


@pytest.mark.asyncio
async def test_manual_replay_raises_not_found_for_missing_delivery(
    db: AsyncSession,
):
    with pytest.raises(DeliveryNotFoundError):
        await manual_delivery(999999, db)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        DeliveryStatus.PENDING,
        DeliveryStatus.PROCESSING,
        DeliveryStatus.AWAITING_RETRY,
        DeliveryStatus.SUCCEEDED,
    ],
)
async def test_manual_replay_raises_not_replayable_for_invalid_status(
    db: AsyncSession,
    status: DeliveryStatus,
):
    delivery = await create_delivery(
        db,
        status=status,
    )

    with pytest.raises(DeliveryNotReplayableError):
        await manual_delivery(delivery.id, db)

    await db.refresh(delivery)

    assert delivery.status == status


@pytest.mark.asyncio
async def test_manual_replay_not_replayable_preserves_delivery(
    db: AsyncSession,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.SUCCEEDED,
    )

    original_attempt_count = delivery.attempt_count
    original_trigger = delivery.queued_trigger

    with pytest.raises(DeliveryNotReplayableError):
        await manual_delivery(delivery.id, db)

    await db.refresh(delivery)

    assert delivery.status == DeliveryStatus.SUCCEEDED
    assert delivery.attempt_count == original_attempt_count
    assert delivery.queued_trigger == original_trigger


@pytest.mark.asyncio
async def test_replay_failed_delivery(client, db: AsyncSession):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.FAILED,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")

    assert response.status_code == 202

    data = response.json()
    assert data["id"] == delivery.id
    assert data["status"] == DeliveryStatus.PENDING.value

    await db.refresh(delivery)

    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert delivery.failure_type is None
    assert delivery.next_retry_at is None
    assert delivery.processing_started_at is None


@pytest.mark.asyncio
async def test_replay_unknown_delivery(client, db: AsyncSession):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.UNKNOWN,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")

    assert response.status_code == 202

    await db.refresh(delivery)

    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.queued_trigger == DeliveryTrigger.MANUAL_REPLAY


@pytest.mark.asyncio
async def test_replay_missing_delivery_returns_404(client):
    response = await client.post("/api/deliveries/999999/replay")

    assert response.status_code == 404
    assert response.json()["detail"] == "Delivery not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        DeliveryStatus.SUCCEEDED,
        DeliveryStatus.PENDING,
        DeliveryStatus.AWAITING_RETRY,
        DeliveryStatus.PROCESSING,
    ],
)
async def test_replay_non_replayable_delivery_returns_409(
    client,
    db: AsyncSession,
    status: DeliveryStatus,
):
    delivery = await create_delivery(
        db,
        status=status,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")

    assert response.status_code == 409
    assert response.json()["detail"] == "Delivery is not replayable"

    await db.refresh(delivery)

    assert delivery.status == status


@pytest.mark.asyncio
async def test_manual_replay_is_recorded_in_attempt_history(
    client,
    db: AsyncSession,
    monkeypatch,
):
    delivery = await create_delivery(
        db,
        status=DeliveryStatus.FAILED,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")

    assert response.status_code == 202

    db.expire_all()

    claimed = await claim_next_delivery(db)

    assert claimed is not None
    assert claimed.id == delivery.id
    assert claimed.status == DeliveryStatus.PROCESSING
    assert claimed.queued_trigger == DeliveryTrigger.MANUAL_REPLAY

    async def fake_execute_delivery_attempt(destination, message):
        return {
            "success": True,
            "external_reference": "manual-replay-test",
        }

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    await process_delivery(
        delivery_id=delivery.id,
        db=db,
    )

    result = await db.execute(
        select(DeliveryAttempt).where(DeliveryAttempt.delivery_id == delivery.id)
    )
    attempts = result.scalars().all()

    assert len(attempts) == 1
    assert attempts[0].trigger == DeliveryTrigger.MANUAL_REPLAY
    assert attempts[0].result == DeliveryAttemptResult.SUCCEEDED

    await db.refresh(delivery)

    assert delivery.status == DeliveryStatus.SUCCEEDED
