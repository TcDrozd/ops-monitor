from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Health status")


class ConfigResponse(BaseModel):
    portainer_base_url: str | None = Field(default=None)
    proxmox_stats_url: str | None = Field(default=None)
    interval: int = Field(ge=1)


class CheckStateResponse(BaseModel):
    id: str
    type: str
    ok: bool | None = None
    last_run: str | None = None
    last_ok: str | None = None
    last_change: str | None = None
    latency_ms: int | None = None
    status_code: int | None = None
    error: str | None = None


class RegistryNormalizedResponse(BaseModel):
    defaults: dict[str, Any]
    checks: dict[str, dict[str, Any]]
    count: int


class StatusSummaryResponse(BaseModel):
    total: int
    up: int
    down: int
    unknown: int
    down_checks: list[CheckStateResponse]


class StatusEventResponse(BaseModel):
    ts: str
    id: str
    event: str
    ok: bool | None = None
    latency_ms: int | None = None
    status_code: int | None = None
    error: str | None = None


class AlertTestResponse(BaseModel):
    ok: bool
    check_id: str
    channel: str
