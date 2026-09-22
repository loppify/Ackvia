import uuid

from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(RegisterRequest):
    pass


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)
