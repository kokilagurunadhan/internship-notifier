from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SubscriptionCreate(BaseModel):

    user_email: EmailStr

    company: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    domain: Optional[str] = Field(
        default=None,
        max_length=255,
    )


class SubscriptionResponse(BaseModel):

    id: int

    user_email: EmailStr

    company: str

    domain: Optional[str] = None

    is_active: bool
    status: str

    model_config = ConfigDict(from_attributes=True)