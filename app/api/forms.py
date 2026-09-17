import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.openapi.utils import status_code_ranges
from pydantic import BaseModel, ConfigDict
from pygments.styles import default
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import SUPPORTED_LANGUAGES, get_locale
from app.database.models import Form, Base, Submission
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


class SubmissionRead(BaseModel):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/{form_id}/submissions", response_model=list[SubmissionRead])
async def get_form_submissions(
        form_id: uuid.UUID,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(get_db),
):
    form = await db.get(Form, form_id)

    if form is None:
        raise HTTPException(status_code=404, detail="Form not foud")

    res = await db.scalars(
        select(Submission)
        .where(Submission.form_id == form_id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return res.all()


@router.get("", response_model=list[FormRead])
async def get_forms(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(get_db),
):
    res = await db.scalars(
        select(Form)
        .order_by(Form.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return res.all()
