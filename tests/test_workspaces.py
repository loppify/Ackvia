import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, Workspace, WorkspaceMembership, WorkspaceRole
from app.database.queries.auth import get_user_by_email
from app.services.workspace import (
    WorkspaceAccessDeniedError,
    get_user_workspace,
    list_user_workspaces,
)


async def test_get_user_workspace_returns_workspace_for_owner(
    db: AsyncSession,
):
    user = User(email="owner@example.com")
    workspace = Workspace(name="Test Workspace")

    membership = WorkspaceMembership(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    db.add(membership)
    await db.flush()

    result = await get_user_workspace(
        db,
        user,
        workspace.id,
    )

    assert result.id == workspace.id


async def test_get_user_workspace_returns_workspace_for_member(
    db: AsyncSession,
):
    user = User(email="member@example.com")
    workspace = Workspace(name="Test Workspace")

    membership = WorkspaceMembership(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    db.add(membership)
    await db.flush()

    result = await get_user_workspace(
        db,
        user,
        workspace.id,
    )

    assert result.id == workspace.id


async def test_get_user_workspace_rejects_user_without_membership(
    db: AsyncSession,
):
    user = User(email="outsider@example.com")
    workspace = Workspace(name="Private Workspace")

    db.add_all([user, workspace])
    await db.flush()

    with pytest.raises(WorkspaceAccessDeniedError):
        await get_user_workspace(
            db,
            user,
            workspace.id,
        )


async def test_get_user_workspace_rejects_membership_in_different_workspace(
    db: AsyncSession,
):
    user = User(email="member@example.com")
    allowed_workspace = Workspace(name="Allowed")
    forbidden_workspace = Workspace(name="Forbidden")

    membership = WorkspaceMembership(
        user=user,
        workspace=allowed_workspace,
        role=WorkspaceRole.MEMBER,
    )

    db.add_all([membership, forbidden_workspace])
    await db.flush()

    with pytest.raises(WorkspaceAccessDeniedError):
        await get_user_workspace(
            db,
            user,
            forbidden_workspace.id,
        )


async def test_list_user_workspaces_returns_accessible_workspaces(
    db: AsyncSession,
):
    user = User(email="user@example.com")
    first = Workspace(name="First")
    second = Workspace(name="Second")

    db.add_all(
        [
            WorkspaceMembership(
                user=user,
                workspace=first,
                role=WorkspaceRole.OWNER,
            ),
            WorkspaceMembership(
                user=user,
                workspace=second,
                role=WorkspaceRole.MEMBER,
            ),
        ]
    )
    await db.commit()

    result = await list_user_workspaces(db, user)

    assert {workspace.id for workspace in result} == {
        first.id,
        second.id,
    }


async def test_list_user_workspaces_does_not_return_foreign_workspace(
    db: AsyncSession,
):
    user = User(email="user@example.com")
    other_user = User(email="other@example.com")

    own_workspace = Workspace(name="Own")
    foreign_workspace = Workspace(name="Foreign")

    db.add_all(
        [
            WorkspaceMembership(
                user=user,
                workspace=own_workspace,
                role=WorkspaceRole.MEMBER,
            ),
            WorkspaceMembership(
                user=other_user,
                workspace=foreign_workspace,
                role=WorkspaceRole.OWNER,
            ),
        ]
    )
    await db.commit()

    result = await list_user_workspaces(db, user)

    assert [workspace.id for workspace in result] == [own_workspace.id]


async def test_list_user_workspaces_returns_empty_list_without_memberships(
    db: AsyncSession,
):
    user = User(email="user@example.com")
    db.add(user)
    await db.flush()

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
    await client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )

    user = await get_user_by_email(db, "user@example.com")

    first = Workspace(name="First")
    second = Workspace(name="Second")

    db.add_all(
        [
            WorkspaceMembership(
                user=user,
                workspace=first,
                role=WorkspaceRole.OWNER,
            ),
            WorkspaceMembership(
                user=user,
                workspace=second,
                role=WorkspaceRole.MEMBER,
            ),
        ]
    )
    await db.commit()

    response = await client.get("/api/workspaces")

    assert response.status_code == 200

    data = response.json()

    assert {workspace["name"] for workspace in data} == {
        "First",
        "Second",
    }


async def test_list_workspaces_does_not_expose_other_users_workspace(
    client,
    db: AsyncSession,
):
    await client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )

    user = await get_user_by_email(db, "user@example.com")

    other_user = User(email="other@example.com")
    own_workspace = Workspace(name="Visible")
    foreign_workspace = Workspace(name="Secret")

    db.add_all(
        [
            WorkspaceMembership(
                user=user,
                workspace=own_workspace,
                role=WorkspaceRole.MEMBER,
            ),
            WorkspaceMembership(
                user=other_user,
                workspace=foreign_workspace,
                role=WorkspaceRole.OWNER,
            ),
        ]
    )
    await db.commit()

    response = await client.get("/api/workspaces")

    assert response.status_code == 200

    names = {workspace["name"] for workspace in response.json()}

    assert "Visible" in names
    assert "Secret" not in names
