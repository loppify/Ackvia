from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.deliveries import DeliveryBase


class SubmissionBase(BaseModel):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionRead(SubmissionBase):
    payload: dict[str, Any]
    deliveries: list[DeliveryBase]
