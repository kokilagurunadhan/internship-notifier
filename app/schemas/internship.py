from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic import EmailStr

class InternshipCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    url: HttpUrl
    description: str | None = Field(default=None, max_length=10000)
    source: str | None = Field(default=None, max_length=100)


class InternshipResponse(BaseModel):
    id: int
    company: str
    title: str
    location: str | None = None
    url: str
    description: str | None = None
    source: str | None = None

    model_config = ConfigDict(from_attributes=True)
class InternshipDismissRequest(BaseModel):
    user_email: EmailStr
