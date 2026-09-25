import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Delivery,
    DeliveryStatus,
    DeliveryTrigger,
    Form,
    Submission,
    WorkspaceMembership,
)


async def get_accessible_submission_by_id(
    db: AsyncSession, submission_id: int, user_id: uuid.UUID
) -> Submission | None:
    return await db.scalar(
        select(Submission)
        .join(Form, Submission.form_id == Form.id)
        .join(
            WorkspaceMembership, Form.workspace_id == WorkspaceMembership.workspace_id
        )
        .options(selectinload(Submission.deliveries))
        .where(Submission.id == submission_id, WorkspaceMembership.user_id == user_id)
    )


async def create_submission(db: AsyncSession, form: Form, payload: dict):
    submission = Submission(form_id=form.id, payload=payload)
    db.add(submission)
    await db.flush()

    for destination in form.destinations:
        db.add(
            Delivery(
                submission_id=submission.id,
                destination_id=destination.id,
                status=DeliveryStatus.PENDING,
                queued_trigger=DeliveryTrigger.AUTOMATIC,
            )
        )
    await db.commit()
    await db.refresh(submission)
    return submission
