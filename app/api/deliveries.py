from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import DeliveryStatus, DeliveryAttemptResult, DeliveryTrigger, FailureType, \
    Delivery
from app.database.session import get_db


class DeliveryAttemptRead(BaseModel):
    id: int
    created_at: datetime
    finished_at: datetime | None
    result: DeliveryAttemptResult | None
    error: str | None
    trigger: DeliveryTrigger

    model_config = ConfigDict(from_attributes=True)


class DeliveryDetailRead(BaseModel):
    id: int
    submission_id: int
    destination_id: int

    status: DeliveryStatus
    attempt_count: int
    failure_type: FailureType | None
    last_error: str | None

    created_at: datetime
    delivered_at: datetime | None
    next_retry_at: datetime | None

    attempts: list[DeliveryAttemptRead]

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])


@router.get("/{delivery_id}", response_model=DeliveryDetailRead)
async def get_detailed_delivery(
        delivery_id: int,
        db: AsyncSession = Depends(get_db),
):
    res = await db.scalar(
        select(Delivery)
        .where(Delivery.id == delivery_id)
        .options(selectinload(Delivery.attempts))
    )

    if res is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    return res
