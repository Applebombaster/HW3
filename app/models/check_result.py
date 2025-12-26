from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel


class CheckResultBase(SQLModel):
    is_up: bool
    status_code: Optional[int] = None
    response_time: Optional[float] = None  # в миллисекундах
    error_message: Optional[str] = None


class CheckResult(CheckResultBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    website_id: int = Field(foreign_key="website.id")
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class CheckCreate(CheckResultBase):
    website_id: int