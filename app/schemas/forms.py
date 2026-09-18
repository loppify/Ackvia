import uuid

from pydantic import BaseModel, ConfigDict


class FormRead(BaseModel):
    id: uuid.UUID
    title: str

    model_config = ConfigDict(from_attributes=True)
