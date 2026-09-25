import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Delivery, Form, Submission, WorkspaceMembership


async def get_accessible_delivery_by_id(
    db: AsyncSession, delivery_id: int, user_id: uuid.UUID
):
    return await db.scalar(
        select(Delivery)
        .join(Submission, Delivery.submission_id == Submission.id)
        .join(Form, Form.id == Submission.form_id)
        .join(
            WorkspaceMembership, WorkspaceMembership.workspace_id == Form.workspace_id
        )
        .options(selectinload(Delivery.attempts))
        .where(Delivery.id == delivery_id, WorkspaceMembership.user_id == user_id)
    )


async def get_delivery_for_processing(
    db: AsyncSession, delivery_id: int
) -> Delivery | None:
    result = await db.execute(
        select(Delivery)
        .where(Delivery.id == delivery_id)
        .options(
            selectinload(Delivery.destination),
            selectinload(Delivery.submission).selectinload(Submission.form),
        )
    )
    return result.scalar_one_or_none()
