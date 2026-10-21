from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    invitation_token: str = Field(min_length=32, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class CreateInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class UserResponse(BaseModel):
    id: UUID
    email: str
    timezone: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationResponse(BaseModel):
    token: str
    email: str
    expires_at: datetime
