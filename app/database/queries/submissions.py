from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Delivery, DeliveryStatus, Form, Submission


async def get_detailed_submission_by_id(db: AsyncSession, submission_id: int):
    return await db.scalar(
        select(Submission)
        .options(selectinload(Submission.deliveries))
        .where(Submission.id == submission_id)
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
            )
        )
    await db.commit()
    await db.refresh(submission)
    return submission
