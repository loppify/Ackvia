from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import DeliveryStatus, Submission
from app.database.session import get_db


class DeliveryRead(BaseModel):
    id: int
    destination_id: int
    status: DeliveryStatus
    attempt_count: int
    last_error: str | None
    delivered_at: datetime | None
    next_retry_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SubmissionRead(BaseModel):
    id: int
    created_at: datetime
    payload: dict[str, Any]
    deliveries: list[DeliveryRead]

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("/{sub_id}", response_model=SubmissionRead)
async def get_detailed_submission(
    sub_id: int,
    db: AsyncSession = Depends(get_db),
):
    res = await db.scalar(
        select(Submission)
        .options(selectinload(Submission.deliveries))
        .where(Submission.id == sub_id)
    )

    if res is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    return res
