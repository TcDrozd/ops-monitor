from __future__ import annotations

from typing import Literal, Optional, List, Dict
from pydantic import BaseModel, Field, AnyHttpUrl

CheckType = Literal["http", "tcp"]

class Defaults(BaseModel):
    interval_s: int = 30
    timeout_s: int = 3
    retries: int = 1

class BaseCheck(BaseModel):
    id: str = Field(..., min_length=1)
    type: CheckType
    tags: List[str] = Field(default_factory=list)
    interval_s: Optional[int] = None
    timeout_s: Optional[int] = None
    connect_timeout_override: Optional[float] = None
    retries: Optional[int] = None
    down_threshold: Optional[int] = Field(default=None, ge=1)

class HttpCheck(BaseCheck):
    type: Literal["http"]
    url: AnyHttpUrl

class TcpCheck(BaseCheck):
    type: Literal["tcp"]
    host: str
    port: int = Field(..., ge=1, le=65535)

Check = HttpCheck | TcpCheck

class Registry(BaseModel):
    defaults: Defaults = Defaults()
    checks: List[Check]
