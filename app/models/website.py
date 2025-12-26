from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from enum import Enum


class ProtocolType(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    PING = "ping"


class WebsiteBase(SQLModel):
    name: str
    url: str
    protocol: ProtocolType = ProtocolType.HTTPS
    check_interval: int = 60  # секунды
    is_active: bool = True


class Website(WebsiteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WebsiteCreate(WebsiteBase):
    pass


class WebsiteUpdate(SQLModel):
    name: Optional[str] = None
    url: Optional[str] = None
    protocol: Optional[ProtocolType] = None
    check_interval: Optional[int] = None
    is_active: Optional[bool] = None