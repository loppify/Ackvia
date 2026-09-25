from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DeliveryStatus, WorkspaceRole
from app.database.queries.submissions import get_accessible_submission_by_id
from tests.conftest import (
    create_authenticated_workspace,
    create_delivery,
    create_form,
    create_membership,
    create_submission,
    create_user,
    create_workspace,
    register_and_get_user,
)


@pytest.mark.asyncio
async def test_get_submission_returns_submission_with_payload(
    db: AsyncSession,
    client: AsyncClient,
):
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )

    await db.commit()

    delivery = await create_delivery(
        db,
        DeliveryStatus.PENDING,
        workspace=workspace,
    )

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )

    await db.commit()

    delivery = await create_delivery(
        db,
        DeliveryStatus.PENDING,
        workspace=workspace,
    )

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )

    await db.commit()

    delivery = await create_delivery(
        db,
        DeliveryStatus.AWAITING_RETRY,
        workspace=workspace,
    )

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
async def test_get_submission_not_found(client: AsyncClient, db: AsyncSession):
    await create_authenticated_workspace(
        client,
        db,
    )

    await db.commit()

    response = await client.get("/api/submissions/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_submission_invalid_id(client: AsyncClient, db: AsyncSession):
    await create_authenticated_workspace(
        client,
        db,
    )

    await db.commit()
    response = await client.get("/api/submissions/not-an-id")

    assert response.status_code == 422


async def test_get_accessible_submission_by_id_returns_submission_for_member(
    db: AsyncSession,
):
    user = await create_user(db)
    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.flush()

    submission = await create_submission(
        db,
        form=form,
        payload={"name": "Alice"},
    )

    result = await get_accessible_submission_by_id(
        db,
        submission.id,
        user.id,
    )

    assert result is not None
    assert result.id == submission.id
    assert result.payload == {"name": "Alice"}


async def test_get_accessible_submission_by_id_returns_submission_for_owner(
    db: AsyncSession,
):
    user = await create_user(db)
    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.flush()

    submission = await create_submission(
        db,
        form=form,
    )

    result = await get_accessible_submission_by_id(
        db,
        submission.id,
        user.id,
    )

    assert result is not None
    assert result.id == submission.id


async def test_get_accessible_submission_by_id_returns_none_for_foreign_workspace(
    db: AsyncSession,
):
    user = await create_user(db)

    other_user = await create_user(
        db,
        email="other@example.com",
    )

    own_workspace = await create_workspace(
        db,
        name="Own",
    )
    foreign_workspace = await create_workspace(
        db,
        name="Foreign",
    )

    await create_membership(
        db,
        user=user,
        workspace=own_workspace,
    )
    await create_membership(
        db,
        user=other_user,
        workspace=foreign_workspace,
    )

    foreign_form = await create_form(
        db,
        workspace=foreign_workspace,
    )
    db.add(foreign_form)
    await db.flush()

    foreign_submission = await create_submission(
        db,
        form=foreign_form,
        payload={"secret": "hidden"},
    )

    result = await get_accessible_submission_by_id(
        db,
        foreign_submission.id,
        user.id,
    )

    assert result is None


async def test_get_accessible_submission_by_id_returns_none_for_unknown_submission(
    db: AsyncSession,
):
    user = await create_user(db)

    result = await get_accessible_submission_by_id(
        db,
        999999999,
        user.id,
    )

    assert result is None


async def test_get_submission_returns_accessible_submission(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.flush()

    submission = await create_submission(
        db,
        form=form,
        payload={
            "name": "Alice",
            "email": "alice@example.com",
        },
    )

    await db.commit()

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == submission.id
    assert data["payload"] == {
        "name": "Alice",
        "email": "alice@example.com",
    }


async def test_get_submission_hides_foreign_workspace_submission(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    other_user = await create_user(
        db,
        email="other@example.com",
    )

    own_workspace = await create_workspace(
        db,
        name="Own",
    )
    foreign_workspace = await create_workspace(
        db,
        name="Foreign",
    )

    await create_membership(
        db,
        user=user,
        workspace=own_workspace,
    )
    await create_membership(
        db,
        user=other_user,
        workspace=foreign_workspace,
    )

    foreign_form = await create_form(
        db,
        workspace=foreign_workspace,
    )
    db.add(foreign_form)
    await db.flush()

    foreign_submission = await create_submission(
        db,
        form=foreign_form,
        payload={"secret": "must-not-leak"},
    )

    await db.commit()

    response = await client.get(f"/api/submissions/{foreign_submission.id}")

    assert response.status_code == 404


async def test_get_submission_returns_404_without_workspace_membership(
    db: AsyncSession,
    client: AsyncClient,
):
    await register_and_get_user(client, db)

    workspace = await create_workspace(db)

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.flush()

    submission = await create_submission(
        db,
        form=form,
    )

    await db.commit()

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 404


async def test_get_submission_requires_authentication(
    db: AsyncSession,
    client: AsyncClient,
):
    workspace = await create_workspace(db)

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.flush()

    submission = await create_submission(
        db,
        form=form,
    )

    await db.commit()

    client.cookies.clear()

    response = await client.get(f"/api/submissions/{submission.id}")

    assert response.status_code == 401
