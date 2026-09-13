import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, NullPool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database.models import (
    Base,
    Delivery,
    DeliveryStatus,
    Destination,
    FailureType,
    Form,
    Submission,
)
from app.database.session import get_db
from app.main import app

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield
    assert "test" in TEST_DATABASE_URL
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_invalid_form_uuid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        random_id = uuid.uuid4()
        res = await ac.post(
            f"/f/{random_id}",
            json={"dummy": "data"},
            headers={"Accept": "application/json"},
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_delivery_states_are_independent():
    async with TestSessionLocal() as session:
        form = Form(
            title="Landing Test",
            language="en",
        )

        destination_a = Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        destination_b = Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        destination_c = Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        submission = Submission(form=form, payload={"name": "Ivan"})
        delivery_a = Delivery(submission=submission, destination=destination_a)
        delivery_b = Delivery(submission=submission, destination=destination_b)
        delivery_c = Delivery(submission=submission, destination=destination_c)
        session.add(form)
        await session.commit()

        delivery_a.status = DeliveryStatus.SUCCEEDED
        delivery_b.status = DeliveryStatus.FAILED
        delivery_b.failure_type = FailureType.PERMANENT
        delivery_c.status = DeliveryStatus.PENDING

        await session.commit()
        await session.refresh(submission)

        result = await session.execute(
            select(Delivery).where(Delivery.submission_id == submission.id)
        )

        deliverys = result.scalars().all()

        assert len(deliverys) == 3
        statuses = {delivery.status for delivery in deliverys}

        assert statuses == {
            DeliveryStatus.SUCCEEDED,
            DeliveryStatus.FAILED,
            DeliveryStatus.PENDING,
        }


@pytest.mark.asyncio
async def test_delivery_creation():
    async with TestSessionLocal() as session:
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
        Delivery(submission=submission, destination=destination)
        session.add(form)
        await session.commit()

        a = await session.scalar(select(Form).order_by(Form.id))
        b = await session.scalar(select(Destination).order_by(Destination.id))
        c = await session.scalar(select(Submission).order_by(Submission.id))
        d = await session.scalar(select(Delivery).order_by(Delivery.id))

        assert a.title == "Landing Test"
        assert b.type == "telegram"
        assert c.payload == {"name": "Ivan"}
        assert d.status == DeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_new_delivery_starts_pending_without_attempts():
    async with TestSessionLocal() as session:
        form = Form(
            title="Landing Test",
            language="en",
        )
        destination = Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        submission = Submission(form=form, payload={"name": "Ivan"})
        Delivery(submission=submission, destination=destination)

        session.add(form)

        await session.commit()

        res = await session.execute(
            select(Delivery).options(selectinload(Delivery.attempts))
        )
        delivery = res.scalar_one()
        assert delivery.status == DeliveryStatus.PENDING
        assert delivery.attempt_count == 0
        assert len(delivery.attempts) == 0


@pytest.mark.asyncio
async def test_duplicate_delivery_failure():
    async with TestSessionLocal() as session:
        form = Form(
            title="Landing Test",
            language="en",
        )
        destination = Destination(
            form=form,
            type="telegram",
            reference="987654321",
        )
        submission = Submission(form=form, payload={"name": "Ivan"})
        Delivery(submission=submission, destination=destination)
        Delivery(submission=submission, destination=destination)

        session.add(form)

        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()

        forms = await session.scalars(select(Form))
        submissions = await session.scalars(select(Submission))
        deliverys = await session.scalars(select(Delivery))

        assert forms.all() == []
        assert submissions.all() == []
        assert deliverys.all() == []

# @pytest.mark.asyncio
# async def test_claim_next_delivery():
