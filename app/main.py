import logging
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.api_schemas import (
    AlertTestResponse,
    CheckStateResponse,
    ConfigResponse,
    HealthResponse,
    OpsHealthResponse,
    OpsSummaryResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportRangeInfo,
    ReportSourcesInfo,
    RegistryNormalizedResponse,
    StatusEventResponse,
    StatusSummaryResponse,
)
from app.clients.ollama_client import OllamaClientError, generate_json_report
from app.notifier import NtfyConfig, NtfyNotifier
from app.models import Registry
from app.ops_logic import (
    compute_overall_status,
    is_fresh,
    serialize_ts,
    summarize_checks,
    utcnow_iso,
)
from app.state import StateStore
from app.runner import loop_forever
from app.config import settings
from app.registry import apply_defaults, load_registry
from app.reporting import (
    REPORT_EVENTS_LIMIT,
    build_fallback_report_data,
    build_facts_payload,
    build_repair_prompt,
    build_report_prompt,
    parse_report_data,
    proxmox_payload_from_cache,
    render_report_markdown,
    validate_report_data,
)

import threading

logger = logging.getLogger(__name__)
store = StateStore(db_path=settings.OPSMONITOR_DB_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    t = threading.Thread(
        target=loop_forever,
        args=(store, settings.MONITOR_INTERVAL),
        daemon=True,
    )
    t.start()
    yield


app = FastAPI(
    title="Ops Monitor",
    version="1.0.0",
    description=(
        "Service checks monitor that loads checks from checks.yml, "
        "runs HTTP/TCP probes, and exposes current status and event history."
    ),
    lifespan=lifespan,
)


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


@app.get(
    "/api/ops/health",
    response_model=OpsHealthResponse,
    tags=["ops"],
    summary="Control-Plane Dependency Health",
    description="Dependency reachability from cached poll/check state only.",
)
def ops_health():
    proxmox_cache = store.proxmox_stats_snapshot()
    proxmox_last_fetch_ts = serialize_ts(proxmox_cache.last_fetch_ts)
    proxmox_fresh = is_fresh(
        last_fetch_ts=proxmox_cache.last_fetch_ts,
        poll_seconds=settings.MONITOR_INTERVAL,
    )

    if proxmox_cache.last_fetch_ts is None:
        proxmox_status = {
            "status": "unknown",
            "last_fetch_ts": None,
            "last_error": proxmox_cache.last_error,
            "note": "proxmox-stats not polled yet",
        }
    elif proxmox_fresh and proxmox_cache.last_error is None:
        proxmox_status = {
            "status": "ok",
            "last_fetch_ts": proxmox_last_fetch_ts,
            "last_error": None,
            "note": None,
        }
    elif proxmox_fresh:
        proxmox_status = {
            "status": "unavailable",
            "last_fetch_ts": proxmox_last_fetch_ts,
            "last_error": proxmox_cache.last_error,
            "note": None,
        }
    else:
        proxmox_status = {
            "status": "unknown",
            "last_fetch_ts": proxmox_last_fetch_ts,
            "last_error": proxmox_cache.last_error,
            "note": "stale proxmox-stats poll data",
        }

    return {
        "timestamp": utcnow_iso(),
        "dependencies": {
            "proxmox_stats": proxmox_status,
            "ntfy": {
                "status": "unknown",
                "note": "ntfy checks not enabled",
            },
            "portainer": {
                "status": "unknown",
                "note": "portainer checks not enabled",
            },
        },
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


@app.post(
    "/api/reports/generate",
    response_model=ReportGenerateResponse,
    tags=["reports"],
    summary="Generate Human Ops Report",
    description="Builds internal facts, asks Ollama for structured JSON, and renders stable markdown.",
)
def reports_generate(request: ReportGenerateRequest) -> ReportGenerateResponse:
    generated_at = utcnow_iso()
    ops_summary_payload = ops_summary()
    status_summary_payload = status_summary()
    events_payload = status_events(limit=REPORT_EVENTS_LIMIT)
    proxmox_payload = proxmox_payload_from_cache(proxmox_cache=store.proxmox_stats_snapshot())

    facts = build_facts_payload(
        ops_summary_payload=ops_summary_payload,
        status_summary_payload=status_summary_payload,
        events_payload=events_payload,
        proxmox_payload=proxmox_payload,
        generated_at=generated_at,
        range_minutes=request.range_minutes,
    )
    prompt = build_report_prompt(facts=facts)
    report_data = None
    markdown = None
    parse_error = None
    report_text = ""
    first_pass_error: str | None = None

    try:
        ollama_payload = generate_json_report(
            prompt,
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout_s=settings.OLLAMA_TIMEOUT_S,
            temperature=0,
        )
    except OllamaClientError as exc:
        first_pass_error = str(exc)
        logger.error("First-pass report generation failed: %s", first_pass_error)
        retry_timeout = max(settings.OLLAMA_TIMEOUT_S * 2, 90)
        try:
            ollama_payload = generate_json_report(
                prompt,
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                timeout_s=retry_timeout,
                temperature=0,
            )
            logger.info("First-pass report generation retry succeeded with timeout=%ss", retry_timeout)
        except OllamaClientError as retry_exc:
            final_error = f"{first_pass_error}; retry failed: {retry_exc}"
            logger.error("First-pass report retry failed: %s", retry_exc)
            parse_error = f"model call failed: {final_error}"
            report_data = build_fallback_report_data(error_text=final_error)
            report_text = ""
            sources_info = {
                "ops_summary_included": True,
                "status_summary_included": True,
                "events_limit": REPORT_EVENTS_LIMIT,
                "proxmox_included": True,
            }
            markdown = render_report_markdown(
                report_data=report_data,
                generated_at=generated_at,
                range_minutes=request.range_minutes,
                status_summary=status_summary_payload,
                sources_info=sources_info,
            )
            return ReportGenerateResponse(
                ok=True,
                generated_at=generated_at,
                inputs=facts,
                report_text=report_text,
                report_json=report_data,
                parse_error=parse_error,
                markdown=markdown,
                range=ReportRangeInfo(
                    range_minutes=request.range_minutes,
                    generated_at=generated_at,
                ),
                sources=ReportSourcesInfo(**sources_info),
            )

    sources_info = {
        "ops_summary_included": True,
        "status_summary_included": True,
        "events_limit": REPORT_EVENTS_LIMIT,
        "proxmox_included": True,
    }

    model_output = ollama_payload.get("response")
    if isinstance(model_output, str):
        report_text = model_output
    else:
        report_text = json.dumps(ollama_payload)

    first_failure_reason: str | None = None
    try:
        first_candidate = parse_report_data(report_text)
        is_valid, validity_reason = validate_report_data(first_candidate)
        if is_valid:
            report_data = first_candidate
            logger.info("Report normalization succeeded on first pass")
        else:
            first_failure_reason = f"first pass validity failed: {validity_reason}"
            logger.warning("Report validity gate failed on first pass: %s", validity_reason)
    except ValueError as exc:
        first_failure_reason = f"first pass normalization failed: {exc}"
        snippet = report_text[:280].replace("\n", "\\n")
        logger.error("Failed to parse report JSON output: %s | snippet=%s", exc, snippet)

    if report_data is None:
        if first_failure_reason is None:
            first_failure_reason = "first pass failed without a specific reason"
        repair_prompt = build_repair_prompt(bad_output=report_text)
        repair_failure_reason: str | None = None
        try:
            repaired_payload = generate_json_report(
                repair_prompt,
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                timeout_s=settings.OLLAMA_TIMEOUT_S,
                temperature=0,
                max_tokens=700,
            )
            repaired_text = repaired_payload.get("response")
            if isinstance(repaired_text, str):
                repair_candidate = parse_report_data(repaired_text)
                repair_valid, repair_validity_reason = validate_report_data(repair_candidate)
                if repair_valid:
                    report_data = repair_candidate
                    parse_error = f"{first_failure_reason}; repaired via second pass"
                    report_text = repaired_text
                    logger.info("Report repair pass succeeded")
                else:
                    repair_failure_reason = f"repair validity failed: {repair_validity_reason}"
            else:
                repair_failure_reason = "repair output missing response text"
        except (OllamaClientError, ValueError) as repair_exc:
            repair_failure_reason = str(repair_exc)
            logger.error("Report repair pass failed: %s", repair_exc)

        if report_data is None:
            parse_error = f"{first_failure_reason}; {repair_failure_reason}"
            logger.warning("Report repair failed; using deterministic fallback")
            report_data = build_fallback_report_data(error_text=parse_error)

    if report_data is not None:
        markdown = render_report_markdown(
            report_data=report_data,
            generated_at=generated_at,
            range_minutes=request.range_minutes,
            status_summary=status_summary_payload,
            sources_info=sources_info,
        )

    return ReportGenerateResponse(
        ok=True,
        generated_at=generated_at,
        inputs=facts,
        report_text=report_text,
        report_json=report_data,
        parse_error=parse_error,
        markdown=markdown,
        range=ReportRangeInfo(
            range_minutes=request.range_minutes,
            generated_at=generated_at,
        ),
        sources=ReportSourcesInfo(**sources_info),
    )
