from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.schemas.workspaces import WorkspaceRead
from app.services.workspace import list_user_workspaces

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceRead], status_code=status.HTTP_200_OK)
async def get_user_workspaces_handler(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await list_user_workspaces(db, user)
