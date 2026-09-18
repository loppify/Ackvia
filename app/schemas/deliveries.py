from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.database.models import (
    DeliveryAttemptResult,
    DeliveryStatus,
    DeliveryTrigger,
    FailureType,
)


class DeliveryAttemptRead(BaseModel):
    id: int
    created_at: datetime
    finished_at: datetime | None
    result: DeliveryAttemptResult | None
    error: str | None
    trigger: DeliveryTrigger

    model_config = ConfigDict(from_attributes=True)


class DeliveryBase(BaseModel):
    id: int
    destination_id: int
    status: DeliveryStatus
    attempt_count: int
    last_error: str | None
    next_retry_at: datetime | None
    delivered_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DeliveryDetailRead(DeliveryBase):
    submission_id: int
    failure_type: FailureType | None
    created_at: datetime
    attempts: list[DeliveryAttemptRead]
