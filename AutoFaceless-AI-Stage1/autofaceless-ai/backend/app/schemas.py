from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    timezone: str = "Asia/Kolkata"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    timezone: str
    daily_quota: int
    model_config = ConfigDict(from_attributes=True)

class JobCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    niche: str = Field(min_length=2, max_length=100)
    language: str = Field(pattern="^(Hindi|Hinglish|Gujarati|English)$")
    format: str = Field(pattern="^(shorts|long-form)$")
    target_duration_seconds: int = Field(ge=15, le=3600)
    tone: str = Field(pattern="^(educational|documentary|entertaining|motivational|storytelling)$")
    topic_keywords: str = Field(default="", max_length=500)
    target_audience: str = Field(default="General audience", max_length=200)

class JobOut(BaseModel):
    id: int
    title: str
    niche: str
    language: str
    format: str
    target_duration_seconds: int
    tone: str
    status: str
    progress: int
    error_message: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DashboardOut(BaseModel):
    timezone: str
    local_date: date
    daily_limit: int
    videos_used_today: int
    remaining_today: int
    queued: int
    processing: int
    completed: int
    failed: int
    jobs: list[JobOut]
