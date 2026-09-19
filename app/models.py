from __future__ import annotations

from typing import Literal, Optional, List

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

CheckType = Literal["http", "tcp", "frigate"]


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


class FrigateCheck(BaseCheck):
    type: Literal["frigate"]
    base_url: AnyHttpUrl
    required_cameras: List[str] = Field(..., min_length=1)
    min_fresh_cameras: int = Field(default=1, ge=1)
    min_recording_storage_mb: float = Field(default=1_500_000, gt=0)
    max_recording_age_s: int = Field(default=120, gt=0)
    startup_grace_s: int = Field(default=120, ge=0)

    @field_validator("required_cameras")
    @classmethod
    def validate_required_cameras(cls, cameras: List[str]) -> List[str]:
        normalized = [camera.strip() for camera in cameras]
        if any(not camera for camera in normalized):
            raise ValueError("required camera names must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("required camera names must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_min_fresh_cameras(self) -> "FrigateCheck":
        if self.min_fresh_cameras > len(self.required_cameras):
            raise ValueError(
                "min_fresh_cameras must not exceed the number of required cameras"
            )
        return self


Check = HttpCheck | TcpCheck | FrigateCheck


class Registry(BaseModel):
    defaults: Defaults = Defaults()
    checks: List[Check]
