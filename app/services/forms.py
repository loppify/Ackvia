import enum

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Form, Destination

class DestinationType(str, enum.Enum):
    TELEGRAM = "telegram"


class DestinationCreate(BaseModel):
    type: DestinationType
    reference: str


class FormCreate(BaseModel):
    title: str
    language: str = "en"
    destinations: list[DestinationCreate]


async def create_form(
        db: AsyncSession, title: str, language: str, destinations: list[DestinationCreate]
):

    form = Form(title=title, language=language)

    for destination_data in destinations:
        destination = Destination(form=form, type=destination_data.type, reference=destination_data.reference)
        db.add(destination)
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form
