import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Form, Submission


async def get_form_by_id(db: AsyncSession, form_id: uuid.UUID):
    return await db.get(Form, form_id)


async def get_form_submissions_from_db(
    db: AsyncSession, form_id: uuid.UUID, limit: int, offset: int
):
    res = await db.scalars(
        select(Submission)
        .where(Submission.form_id == form_id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return res.all()


async def get_all_forms(db: AsyncSession, limit: int, offset: int):
    res = await db.scalars(
        select(Form).order_by(Form.created_at.desc()).offset(offset).limit(limit)
    )
    return res.all()


async def get_form_with_destination(db: AsyncSession, form_id: uuid.UUID):
    result = await db.execute(
        select(Form).where(Form.id == form_id).options(selectinload(Form.destinations))
    )
    form_obj = result.scalar_one_or_none()
    return form_obj
