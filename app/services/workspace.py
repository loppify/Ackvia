import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, Workspace
from app.database.queries.workspace import (
    get_user_workspaces,
    get_workspace_membership_by_user_and_workspace_id,
)


class WorkspaceAccessDeniedError(Exception):
    pass


async def get_user_workspace(
    db: AsyncSession, user: User, workspace_id: uuid.UUID
) -> Workspace:
    workspace_membership = await get_workspace_membership_by_user_and_workspace_id(
        db, user.id, workspace_id
    )
    if workspace_membership is None:
        raise WorkspaceAccessDeniedError

    return workspace_membership.workspace


async def list_user_workspaces(db: AsyncSession, user: User) -> list[Workspace]:
    return await get_user_workspaces(db, user.id)
