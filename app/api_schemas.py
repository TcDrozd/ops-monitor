from __future__ import annotations

from typing import Any, Literal
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


class OpsServicesSummary(BaseModel):
    up: int
    down: int
    down_list: list[str]


class OpsProxmoxSummary(BaseModel):
    status: Literal["ok", "warn", "crit", "unknown", "unavailable"]
    issues: list[dict[str, Any]] = Field(default_factory=list)
    last_fetch_ts: str | None = None
    last_error: str | None = None


class OpsDockerSummary(BaseModel):
    status: Literal["unknown"]
    note: str


class OpsRecentEvent(BaseModel):
    ts: str
    id: str
    event: str


class OpsSummaryResponse(BaseModel):
    timestamp: str
    overall: Literal["ok", "warn", "crit"]
    services: OpsServicesSummary
    proxmox: OpsProxmoxSummary
    docker: OpsDockerSummary
    recent_events: list[OpsRecentEvent]


class OpsDependencyStatus(BaseModel):
    status: Literal["ok", "unknown", "unavailable"]
    last_fetch_ts: str | None = None
    last_error: str | None = None
    note: str | None = None


class OpsDependencyPlaceholder(BaseModel):
    status: Literal["unknown"]
    note: str


class OpsDependenciesResponse(BaseModel):
    proxmox_stats: OpsDependencyStatus
    ntfy: OpsDependencyPlaceholder
    portainer: OpsDependencyPlaceholder


class OpsHealthResponse(BaseModel):
    timestamp: str
    dependencies: OpsDependenciesResponse
