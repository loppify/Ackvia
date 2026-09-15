import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import SUPPORTED_LANGUAGES, get_locale
from app.database.session import get_db
from app.services.forms import FormCreate, create_form

router = APIRouter(prefix="/api/forms", tags=["forms"])


class FormRead(BaseModel):
    id: uuid.UUID
    title: str

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=FormRead, status_code=status.HTTP_201_CREATED)
async def create_form_endpoint(
    data: FormCreate,
    locale: Annotated[tuple[str, dict[str, str]], Depends(get_locale)],
    db: AsyncSession = Depends(get_db),
):
    current_lang, _ = locale
    lang = data.language if data.language in SUPPORTED_LANGUAGES else current_lang

    return await create_form(db, data.title, lang, data.destinations)
