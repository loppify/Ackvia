import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import SUPPORTED_LANGUAGES, get_locale
from app.database.queries.forms import (
    get_all_forms,
    get_form_by_id,
    get_form_submissions_from_db,
)
from app.database.session import get_db
from app.schemas.forms import FormRead
from app.schemas.submissions import SubmissionBase
from app.services.forms import FormCreate, create_form

router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.post("", response_model=FormRead, status_code=status.HTTP_201_CREATED)
async def create_form_endpoint(
        data: FormCreate,
        locale: Annotated[tuple[str, dict[str, str]], Depends(get_locale)],
        db: AsyncSession = Depends(get_db),
):
    current_lang, _ = locale
    lang = data.language if data.language in SUPPORTED_LANGUAGES else current_lang

    return await create_form(db, data.title, lang, data.destinations)


@router.get("/{form_id}/submissions", response_model=list[SubmissionBase])
async def get_form_submissions(
        form_id: uuid.UUID,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(get_db),
):
    form = await get_form_by_id(db, form_id)

    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not foud")

    return await get_form_submissions_from_db(
        db=db, form_id=form_id, limit=limit, offset=offset
    )


@router.get("", response_model=list[FormRead])
async def get_forms(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(get_db),
):
    return await get_all_forms(db=db, limit=limit, offset=offset)
