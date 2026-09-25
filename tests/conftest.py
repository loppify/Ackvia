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
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)
from app.database.queries.auth import get_user_by_email
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
    workspace: Workspace | None = None,
    created_at=None,
) -> Form:
    workspace = Workspace(name="Test Workspace") if workspace is None else workspace
    form = Form(title=title, language=language, workspace=workspace)

    if created_at is not None:
        form.created_at = created_at

    return form


async def create_delivery(
    db: AsyncSession,
    status: DeliveryStatus = DeliveryStatus.PENDING,
    workspace: Workspace | None = None,
) -> Delivery:
    form = await create_form(db, workspace=workspace)
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


async def create_user(
    db: AsyncSession,
    *,
    email: str = "user@example.com",
) -> User:
    user = User(email=email)
    db.add(user)
    await db.flush()
    return user


async def create_workspace(
    db: AsyncSession,
    *,
    name: str = "Test Workspace",
) -> Workspace:
    workspace = Workspace(name=name)
    db.add(workspace)
    await db.flush()
    return workspace


async def create_membership(
    db: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    role: WorkspaceRole = WorkspaceRole.MEMBER,
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        user=user,
        workspace=workspace,
        role=role,
    )
    db.add(membership)
    await db.flush()
    return membership


async def register_and_get_user(
    client: AsyncClient,
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    password: str = "strong-password",
) -> User:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201

    user = await get_user_by_email(db, email)
    assert user is not None

    return user


async def create_submission(
    db: AsyncSession,
    *,
    form: Form,
    payload: dict | None = None,
) -> Submission:
    submission = Submission(
        form=form,
        payload=payload or {"name": "Test User"},
    )
    db.add(submission)
    await db.flush()

    return submission


async def create_authenticated_workspace(
    client: AsyncClient,
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[User, Workspace]:
    user = await register_and_get_user(
        client,
        db,
        email=email,
    )

    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=role,
    )

    return user, workspace
