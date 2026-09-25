import uuid

from pydantic import BaseModel


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
