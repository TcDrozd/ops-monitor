from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


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
    fail_count: int = 0
    down_threshold: int = 1
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


class ReportGenerateRequest(BaseModel):
    range_minutes: int = Field(default=1440, ge=5, le=10080)


class ReportNotableEvent(BaseModel):
    time: str | None = None
    summary: str = ""
    severity: str = "info"
    model_config = ConfigDict(extra="allow")


class ReportIssue(BaseModel):
    summary: str = ""
    suggestion: str = ""
    model_config = ConfigDict(extra="allow")


class ReportData(BaseModel):
    headline: str = "Ops Report"
    notable_events: list[ReportNotableEvent] = Field(default_factory=list)
    current_issues: list[ReportIssue] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


class ReportRangeInfo(BaseModel):
    range_minutes: int
    generated_at: str


class ReportSourcesInfo(BaseModel):
    ops_summary_included: bool
    status_summary_included: bool
    events_limit: int
    proxmox_included: bool


class ReportGenerateResponse(BaseModel):
    ok: bool
    generated_at: str
    inputs: dict[str, Any]
    report_text: str
    report_json: ReportData | None = None
    parse_error: str | None = None
    markdown: str | None = None
    range: ReportRangeInfo
    sources: ReportSourcesInfo


def _report_json_schema() -> dict[str, Any]:
    # Pydantic v2 exposes model_json_schema(); v1 exposes schema().
    schema_fn = getattr(ReportData, "model_json_schema", None)
    if callable(schema_fn):
        return schema_fn()
    return ReportData.schema()  # type: ignore[attr-defined]


REPORT_JSON_SCHEMA: dict[str, Any] = _report_json_schema()
