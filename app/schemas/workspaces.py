import uuid

from pydantic import BaseModel, Field


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
