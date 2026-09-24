import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Form, Submission, Workspace, WorkspaceRole
from app.database.queries.auth import get_user_by_email
from app.database.queries.forms import get_accessible_form_by_id
from app.services.workspace import list_user_workspaces
from tests.conftest import (
    create_authenticated_workspace,
    create_form,
    create_membership,
    create_user,
    create_workspace,
    register_and_get_user,
)


@pytest.mark.asyncio
async def test_invalid_form_uuid(client: AsyncClient):
    random_id = uuid.uuid4()

    response = await client.post(
        f"/f/{random_id}",
        json={"dummy": "data"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_form_submissions_returns_only_its_submissions(
    db: AsyncSession,
    client: AsyncClient,
):
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )
    form = await create_form(db, title="Test form", workspace=workspace)

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )
    form_1 = await create_form(db, title="Form 1", workspace=workspace)
    form_2 = await create_form(db, title="Form 2", workspace=workspace)

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )
    form = await create_form(db, title="Test form", workspace=workspace)

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )
    form = await create_form(db, title="Test form", workspace=workspace)

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
    _, workspace = await create_authenticated_workspace(
        client,
        db,
    )
    form = await create_form(db, title="Test form", workspace=workspace)

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
    client: AsyncClient, db: AsyncSession
):
    await create_authenticated_workspace(
        client,
        db,
    )
    form_id = uuid.uuid4()

    response = await client.get(f"/api/forms/{form_id}/submissions")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_form_belongs_to_workspace(db: AsyncSession) -> None:
    form = await create_form(db, title="Contact Form")
    await db.commit()

    assert form.workspace_id == form.workspace.id


@pytest.mark.asyncio
async def test_workspace_contains_forms(db: AsyncSession) -> None:
    workspace = Workspace(name="Agency Workspace")
    first = Form(title="Contact Form", workspace=workspace)
    second = Form(title="Quote Form", workspace=workspace)
    db.add_all([first, second])
    await db.commit()

    await db.refresh(workspace, ["forms"])
    assert len(workspace.forms) == 2
    assert {form.title for form in workspace.forms} == {"Contact Form", "Quote Form"}


@pytest.mark.asyncio
async def test_form_cannot_exist_without_workspace(db: AsyncSession) -> None:
    from app.database.models import Form

    db.add(Form(title="Orphan Form"))
    with pytest.raises(Exception):
        await db.commit()
    await db.rollback()


async def test_list_forms_requires_authentication(client):
    client.cookies.clear()

    response = await client.get("/api/forms")

    assert response.status_code == 401


async def test_list_user_workspaces_returns_accessible_workspaces(
    db: AsyncSession,
):
    user = await create_user(db)

    first = await create_workspace(db, name="First")
    second = await create_workspace(db, name="Second")

    await create_membership(
        db,
        user=user,
        workspace=first,
        role=WorkspaceRole.OWNER,
    )
    await create_membership(
        db,
        user=user,
        workspace=second,
        role=WorkspaceRole.MEMBER,
    )

    result = await list_user_workspaces(db, user)

    assert {workspace.id for workspace in result} == {
        first.id,
        second.id,
    }


async def test_list_user_workspaces_does_not_return_foreign_workspace(
    db: AsyncSession,
):
    user = await create_user(
        db,
        email="user@example.com",
    )
    other_user = await create_user(
        db,
        email="other@example.com",
    )

    own_workspace = await create_workspace(db, name="Own")
    foreign_workspace = await create_workspace(db, name="Foreign")

    await create_membership(
        db,
        user=user,
        workspace=own_workspace,
    )
    await create_membership(
        db,
        user=other_user,
        workspace=foreign_workspace,
        role=WorkspaceRole.OWNER,
    )

    result = await list_user_workspaces(db, user)

    assert [workspace.id for workspace in result] == [
        own_workspace.id,
    ]


async def test_list_user_workspaces_returns_empty_list_without_memberships(
    db: AsyncSession,
):
    user = await create_user(db)

    result = await list_user_workspaces(db, user)

    assert result == []


async def test_list_workspaces_requires_authentication(client):
    client.cookies.clear()

    response = await client.get("/api/workspaces")

    assert response.status_code == 401


async def test_list_workspaces_returns_current_user_workspaces(
    client,
    db: AsyncSession,
):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    user = await get_user_by_email(
        db,
        "user@example.com",
    )
    assert user is not None

    first = await create_workspace(db, name="First")
    second = await create_workspace(db, name="Second")

    await create_membership(
        db,
        user=user,
        workspace=first,
        role=WorkspaceRole.OWNER,
    )
    await create_membership(
        db,
        user=user,
        workspace=second,
        role=WorkspaceRole.MEMBER,
    )

    # HTTP request uses another AsyncSession.
    await db.commit()

    response = await client.get("/api/workspaces")

    assert response.status_code == 200

    data = response.json()

    assert {workspace["id"] for workspace in data} == {
        str(first.id),
        str(second.id),
    }
    assert {workspace["name"] for workspace in data} == {
        "First",
        "Second",
    }


async def test_list_workspaces_does_not_expose_other_users_workspace(
    client,
    db: AsyncSession,
):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    user = await get_user_by_email(
        db,
        "user@example.com",
    )
    assert user is not None

    other_user = await create_user(
        db,
        email="other@example.com",
    )

    own_workspace = await create_workspace(
        db,
        name="Visible",
    )
    foreign_workspace = await create_workspace(
        db,
        name="Secret",
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
        role=WorkspaceRole.OWNER,
    )

    await db.commit()

    response = await client.get("/api/workspaces")

    assert response.status_code == 200

    data = response.json()
    ids = {workspace["id"] for workspace in data}

    assert str(own_workspace.id) in ids
    assert str(foreign_workspace.id) not in ids


async def test_get_forms_returns_forms(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    workspace = await create_workspace(db)
    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    form_1 = await create_form(
        db,
        title="Form 1",
        workspace=workspace,
    )
    form_2 = await create_form(
        db,
        title="Form 2",
        workspace=workspace,
    )

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


async def test_get_forms_are_ordered_newest_first(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    workspace = await create_workspace(db)
    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    now = datetime.now(timezone.utc)

    old_form = await create_form(
        db,
        title="Old form",
        workspace=workspace,
        created_at=now - timedelta(hours=1),
    )
    new_form = await create_form(
        db,
        title="New form",
        workspace=workspace,
        created_at=now,
    )

    db.add_all([old_form, new_form])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    data = response.json()

    assert [item["id"] for item in data] == [
        str(new_form.id),
        str(old_form.id),
    ]


async def test_get_forms_respects_limit_and_offset(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    workspace = await create_workspace(db)
    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    now = datetime.now(timezone.utc)

    forms = [
        await create_form(
            db,
            title=f"Form {i}",
            workspace=workspace,
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

    assert [item["id"] for item in data] == [
        str(forms[3].id),
        str(forms[2].id),
    ]


async def test_get_forms_returns_empty_list_when_no_forms_exist(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    workspace = await create_workspace(db)
    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_forms_returns_only_forms_from_accessible_workspaces(
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
        name="Own Workspace",
    )
    foreign_workspace = await create_workspace(
        db,
        name="Foreign Workspace",
    )

    await create_membership(
        db,
        user=user,
        workspace=own_workspace,
        role=WorkspaceRole.OWNER,
    )
    await create_membership(
        db,
        user=other_user,
        workspace=foreign_workspace,
        role=WorkspaceRole.OWNER,
    )

    own_form = await create_form(
        db,
        title="Visible",
        workspace=own_workspace,
    )
    foreign_form = await create_form(
        db,
        title="Secret",
        workspace=foreign_workspace,
    )

    db.add_all([own_form, foreign_form])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    ids = {item["id"] for item in response.json()}

    assert str(own_form.id) in ids
    assert str(foreign_form.id) not in ids


async def test_list_forms_member_can_access_workspace_forms(
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
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    ids = {item["id"] for item in response.json()}
    assert str(form.id) in ids


async def test_list_forms_returns_forms_from_multiple_accessible_workspaces(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    first_workspace = await create_workspace(db, name="First")
    second_workspace = await create_workspace(db, name="Second")

    await create_membership(
        db,
        user=user,
        workspace=first_workspace,
        role=WorkspaceRole.OWNER,
    )
    await create_membership(
        db,
        user=user,
        workspace=second_workspace,
        role=WorkspaceRole.MEMBER,
    )

    first_form = await create_form(
        db,
        title="First Form",
        workspace=first_workspace,
    )
    second_form = await create_form(
        db,
        title="Second Form",
        workspace=second_workspace,
    )

    db.add_all([first_form, second_form])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    ids = {item["id"] for item in response.json()}

    assert ids == {
        str(first_form.id),
        str(second_form.id),
    }


async def test_get_accessible_form_by_id_returns_form_for_owner(
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

    result = await get_accessible_form_by_id(
        db,
        form.id,
        user.id,
    )

    assert result is not None
    assert result.id == form.id


async def test_get_accessible_form_by_id_returns_form_for_member(
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

    result = await get_accessible_form_by_id(
        db,
        form.id,
        user.id,
    )

    assert result is not None
    assert result.id == form.id


async def test_get_accessible_form_by_id_returns_none_for_foreign_workspace(
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
        role=WorkspaceRole.OWNER,
    )
    await create_membership(
        db,
        user=other_user,
        workspace=foreign_workspace,
        role=WorkspaceRole.OWNER,
    )

    foreign_form = await create_form(
        db,
        workspace=foreign_workspace,
    )
    db.add(foreign_form)
    await db.flush()

    result = await get_accessible_form_by_id(
        db,
        foreign_form.id,
        user.id,
    )

    assert result is None


async def test_get_accessible_form_by_id_returns_none_for_unknown_form(
    db: AsyncSession,
):
    user = await create_user(db)

    result = await get_accessible_form_by_id(
        db,
        uuid.uuid4(),
        user.id,
    )

    assert result is None


async def test_get_form_submissions_returns_submissions_for_member(
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

    submission = Submission(
        form=form,
        payload={"name": "Alice"},
    )
    db.add(submission)

    # HTTP request has another DB session.
    await db.commit()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == submission.id
    assert data[0]["payload"] == {"name": "Alice"}


async def test_get_form_submissions_rejects_membership_in_different_workspace(
    db: AsyncSession,
    client: AsyncClient,
):
    user = await register_and_get_user(client, db)

    allowed_workspace = await create_workspace(
        db,
        name="Allowed",
    )
    forbidden_workspace = await create_workspace(
        db,
        name="Forbidden",
    )

    await create_membership(
        db,
        user=user,
        workspace=allowed_workspace,
    )

    forbidden_form = await create_form(
        db,
        workspace=forbidden_workspace,
    )
    db.add(forbidden_form)

    await db.commit()

    response = await client.get(f"/api/forms/{forbidden_form.id}/submissions")

    assert response.status_code == 404


async def test_get_form_submissions_requires_authentication(
    db: AsyncSession,
    client: AsyncClient,
):
    workspace = await create_workspace(db)

    form = await create_form(
        db,
        workspace=workspace,
    )
    db.add(form)
    await db.commit()

    client.cookies.clear()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 401
