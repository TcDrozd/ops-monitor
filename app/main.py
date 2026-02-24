from fastapi import FastAPI, HTTPException, Query

from app.api_schemas import (
    AlertTestResponse,
    CheckStateResponse,
    ConfigResponse,
    HealthResponse,
    OpsSummaryResponse,
    RegistryNormalizedResponse,
    StatusEventResponse,
    StatusSummaryResponse,
)
from app.notifier import NtfyConfig, NtfyNotifier
from app.models import Registry
from app.ops_logic import compute_overall_status, serialize_ts, summarize_checks, utcnow_iso
from app.state import StateStore
from app.runner import loop_forever
from app.config import settings
from app.registry import apply_defaults, load_registry

import threading

app = FastAPI(
    title="Ops Monitor",
    version="1.0.0",
    description=(
        "Service checks monitor that loads checks from checks.yml, "
        "runs HTTP/TCP probes, and exposes current status and event history."
    ),
)
store = StateStore(db_path=settings.OPSMONITOR_DB_PATH)


@app.on_event("startup")
def start_runner():
    t = threading.Thread(
        target=loop_forever,
        args=(store, settings.MONITOR_INTERVAL),
        daemon=True,
    )
    t.start()


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health Check",
    description="Liveness endpoint used by probes and orchestration.",
)
def health():
    return {"status": "ok"}


@app.get(
    "/config",
    response_model=ConfigResponse,
    tags=["system"],
    summary="Current Effective Config",
    description="Returns non-secret runtime config values.",
)
def config():
    return {
        "portainer_base_url": settings.PORTAINER_BASE_URL,
        "proxmox_stats_url": settings.PROXMOX_STATS_URL,
        "interval": settings.MONITOR_INTERVAL,
    }


@app.get(
    "/api/registry/raw",
    response_model=Registry,
    tags=["registry"],
    summary="Raw Registry",
    description="Returns the checks registry exactly as parsed from checks.yml.",
)
def registry_raw():
    reg = load_registry()
    return reg.model_dump()


@app.get(
    "/api/registry",
    response_model=RegistryNormalizedResponse,
    tags=["registry"],
    summary="Normalized Registry",
    description="Returns checks with defaults applied, keyed by check id.",
)
def registry_normalized():
    reg = load_registry()
    return {
        "defaults": reg.defaults.model_dump(),
        "checks": apply_defaults(reg),
        "count": len(reg.checks),
    }


@app.get(
    "/api/status/checks",
    response_model=dict[str, CheckStateResponse],
    tags=["status"],
    summary="Current Check States",
    description="Latest known state per check id.",
)
def status_checks():
    return store.snapshot()


@app.get(
    "/api/status/summary",
    response_model=StatusSummaryResponse,
    tags=["status"],
    summary="Status Summary",
    description="Aggregate counts and list of currently down checks.",
)
def status_summary():
    return store.summary()


@app.get(
    "/api/status/events",
    response_model=list[StatusEventResponse],
    tags=["status"],
    summary="Recent Status Events",
    description="Recent INIT/UP/DOWN events, newest first.",
)
def status_events(
    limit: int = Query(default=50, ge=1, le=500, description="Max number of events to return")
):
    return store.events(limit=limit)


@app.get(
    "/api/ops/summary",
    response_model=OpsSummaryResponse,
    tags=["ops"],
    summary="Unified Ops Summary",
    description="Unified control-plane summary for checks, proxmox status, and recent events.",
)
def ops_summary():
    checks = store.snapshot()
    up, down, down_list, core_down, non_core_down = summarize_checks(
        check_results=checks,
        core_check_ids=set(settings.OPS_CORE_CHECK_IDS),
    )

    proxmox_cache = store.proxmox_stats_snapshot()
    proxmox_payload = proxmox_cache.last_payload if isinstance(proxmox_cache.last_payload, dict) else {}
    proxmox_status = proxmox_payload.get("status")
    if proxmox_status not in {"ok", "warn", "crit", "unknown", "unavailable"}:
        proxmox_status = "unknown"

    issues = proxmox_payload.get("issues")
    if not isinstance(issues, list):
        issues = []
    issues = [issue for issue in issues if isinstance(issue, dict)]

    overall = compute_overall_status(
        core_down=core_down,
        non_core_down=non_core_down,
        proxmox_status=proxmox_status,
    )

    recent_events = [
        {"ts": event["ts"], "id": event["id"], "event": event["event"]}
        for event in store.events(limit=20)
    ]

    return {
        "timestamp": utcnow_iso(),
        "overall": overall,
        "services": {
            "up": up,
            "down": down,
            "down_list": down_list,
        },
        "proxmox": {
            "status": proxmox_status,
            "issues": issues,
            "last_fetch_ts": serialize_ts(proxmox_cache.last_fetch_ts),
            "last_error": proxmox_cache.last_error,
        },
        "docker": {
            "status": "unknown",
            "note": "portainer checks not enabled",
        },
        "recent_events": recent_events,
    }


@app.post(
    "/api/alerts/test",
    response_model=AlertTestResponse,
    tags=["alerts"],
    summary="Send Test Alert",
    description="Sends a test ntfy notification for a specific check id.",
)
def alerts_test(
    check_id: str = Query(
        ...,
        min_length=1,
        description="Check id from /api/registry to use as test context",
    )
):
    if not settings.NTFY_URL or not settings.NTFY_TOPIC:
        raise HTTPException(
            status_code=400,
            detail="NTFY_URL and NTFY_TOPIC must be configured",
        )

    checks = apply_defaults(load_registry())
    check = checks.get(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail=f"Unknown check_id: {check_id}")

    target = check["url"] if check["type"] == "http" else f"{check['host']}:{check['port']}"
    title = f"[TEST] {check_id}"
    message = (
        "This is a test notification from ops-monitor.\n"
        f"Check: {check_id} ({check['type']})\n"
        f"Target: {target}"
    )

    notifier = NtfyNotifier(NtfyConfig(base_url=settings.NTFY_URL, topic=settings.NTFY_TOPIC))
    notifier.send_down(title=title, message=message)
    return {"ok": True, "check_id": check_id, "channel": "ntfy"}
