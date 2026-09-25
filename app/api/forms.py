import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.i18n import SUPPORTED_LANGUAGES, get_locale
from app.database.models import User
from app.database.queries.forms import (
    get_accessible_form_by_id,
    get_all_forms,
    get_form_submissions_from_db,
)
from app.database.session import get_db
from app.exceptions import WorkspaceNotFoundError
from app.schemas.forms import FormRead
from app.schemas.submissions import SubmissionRead
from app.services.forms import FormCreate, create_form

router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.post("", response_model=FormRead, status_code=status.HTTP_201_CREATED)
async def create_form_endpoint(
    data: FormCreate,
    locale: Annotated[tuple[str, dict[str, str]], Depends(get_locale)],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_lang, _ = locale
    lang = data.language if data.language in SUPPORTED_LANGUAGES else current_lang

    try:
        form = await create_form(
            db, data.title, lang, data.destinations, user.id, data.workspace_id
        )
        return form
    except WorkspaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


@router.get("/{form_id}/submissions", response_model=list[SubmissionRead])
async def get_form_submissions(
    form_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    form = await get_accessible_form_by_id(db, form_id, user.id)

    if form is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not foud"
        )

    return await get_form_submissions_from_db(
        db=db, form_id=form_id, limit=limit, offset=offset
    )


@router.get("", response_model=list[FormRead])
async def get_forms(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_all_forms(db=db, limit=limit, offset=offset, user_id=user.id)
