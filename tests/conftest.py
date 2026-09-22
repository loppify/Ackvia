import os

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import (
    Base,
    Delivery,
    DeliveryStatus,
    DeliveryTrigger,
    Destination,
    FailureType,
    Form,
    Submission,
    Workspace,
)
from app.database.session import get_db
from app.main import app

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


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
            transport=transport,
            base_url="https://test",
    ) as client:
        yield client


@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_form(
        db: AsyncSession,
        *,
        title: str = "Test form",
        language: str = "en",
        created_at=None,
) -> Form:
    workspace = Workspace(name="Test Workspace")
    form = Form(title=title, language=language, workspace=workspace)

    if created_at is not None:
        form.created_at = created_at

    return form


async def create_delivery(
        db: AsyncSession,
        status: DeliveryStatus = DeliveryStatus.PENDING,
) -> Delivery:
    form = await create_form(db)
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
