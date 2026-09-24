import enum
import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Destination, Form
from app.database.queries.workspace import get_accessible_workspace_by_id


class DestinationType(str, enum.Enum):
    TELEGRAM = "telegram"


class DestinationCreate(BaseModel):
    type: DestinationType
    reference: str


class FormCreate(BaseModel):
    title: str
    language: str = "en"
    destinations: list[DestinationCreate]
    workspace_id: uuid.UUID


class WorkspaceNotFoundError(Exception):
    pass


async def create_form(
    db: AsyncSession,
    title: str,
    language: str,
    destinations: list[DestinationCreate],
    user_id,
    workspace_id,
) -> Form:
    workspace = await get_accessible_workspace_by_id(db, user_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError()

    form = Form(title=title, language=language, workspace=workspace)

    for destination_data in destinations:
        destination = Destination(
            form=form, type=destination_data.type, reference=destination_data.reference
        )
        db.add(destination)
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form
