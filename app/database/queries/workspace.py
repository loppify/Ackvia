import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Workspace, WorkspaceMembership


async def get_workspace_membership_by_user_and_workspace_id(
    db: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> WorkspaceMembership | None:
    workspace_membership = await db.scalar(
        select(WorkspaceMembership)
        .options(selectinload(WorkspaceMembership.workspace))
        .where(
            WorkspaceMembership.workspace_id == workspace_id
            and WorkspaceMembership.user_id == user_id
        )
    )

    return workspace_membership


async def get_user_workspaces(db: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    workspace_memberships = await db.execute(
        select(Workspace)
        .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == user_id)
    )
    return [wm for wm in workspace_memberships.scalars()]


async def get_accessible_workspace_by_id(
    db: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> Workspace | None:
    return await db.scalar(
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(Workspace.id == workspace_id, WorkspaceMembership.user_id == user_id)
    )
