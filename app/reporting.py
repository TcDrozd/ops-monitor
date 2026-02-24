from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.api_schemas import REPORT_JSON_SCHEMA, ReportData
from app.ops_logic import serialize_ts


REPORT_EVENTS_LIMIT = 200
MAX_ITEMS = 20
MAX_TEXT_LEN = 500
MAX_HEADLINE_LEN = 200

SEVERITY_MAP = {
    "info": "info",
    "informational": "info",
    "notice": "info",
    "warn": "warn",
    "warning": "warn",
    "crit": "crit",
    "critical": "crit",
    "error": "crit",
}


def build_facts_payload(
    *,
    ops_summary_payload: dict[str, Any],
    status_summary_payload: dict[str, Any],
    events_payload: list[dict[str, Any]],
    proxmox_payload: dict[str, Any],
    generated_at: str,
    range_minutes: int,
) -> dict[str, Any]:
    return {
        "ops_summary": ops_summary_payload,
        "status_summary": status_summary_payload,
        "events": events_payload,
        "proxmox": proxmox_payload,
        "generated_at": generated_at,
        "range_minutes": range_minutes,
    }


def build_report_prompt(*, facts: dict[str, Any]) -> str:
    schema_example = {
        "headline": "Health Checks",
        "notable_events": [
            {
                "time": None,
                "summary": "X failed to connect.",
                "severity": "warn",
            }
        ],
        "current_issues": [
            {
                "summary": "Dashboards disk usage high (91.7%).",
                "suggestion": "",
            }
        ],
        "recommendations": ["Check Ollama-lab connection."],
    }
    return (
        "Generate a concise operations report from provided facts only.\n"
        "Output a single JSON object.\n"
        "ONLY these top-level keys: headline, notable_events, current_issues, recommendations.\n"
        "If unknown, use empty arrays/empty strings.\n"
        "No additional keys. No prose.\n"
        "Example output:\n"
        f"{json.dumps(schema_example, indent=2)}\n\n"
        "Internal facts:\n"
        "```json\n"
        f"{json.dumps(facts, indent=2)}\n"
        "```\n"
        "Respond ONLY with a JSON object that strictly conforms to this schema:\n"
        f"{json.dumps(REPORT_JSON_SCHEMA, separators=(',', ':'))}"
    )


def build_repair_prompt(*, bad_output: str) -> str:
    return (
        "The following blob must be converted into a valid JSON object matching this schema.\n"
        "Return ONLY the JSON.\n"
        "Blob:\n"
        "```text\n"
        f"{bad_output}\n"
        "```\n"
        "Schema:\n"
        f"{json.dumps(REPORT_JSON_SCHEMA, separators=(',', ':'))}"
    )


def extract_first_json_object(raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return payload
    except ValueError:
        pass

    start = raw_text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    depth = 0
    in_string = False
    escaping = False
    end = -1
    for idx in range(start, len(raw_text)):
        ch = raw_text[idx]
        if in_string:
            if escaping:
                escaping = False
                continue
            if ch == "\\":
                escaping = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break

    if end == -1:
        raise ValueError("Unterminated JSON object")

    extracted = raw_text[start:end]
    payload = json.loads(extracted)
    if not isinstance(payload, dict):
        raise ValueError("Extracted JSON is not an object")
    return payload


def _json_loads_with_nested_string(raw_text: str) -> Any:
    payload = json.loads(raw_text)
    if isinstance(payload, str):
        payload = json.loads(payload)
    return payload


def _coerce_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_severity(value: Any) -> str:
    raw = _coerce_text(value, default="").strip().lower()
    return SEVERITY_MAP.get(raw, "info")


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _top_level_value(payload: dict[str, Any], canonical_key: str, aliases: tuple[str, ...]) -> Any:
    if canonical_key in payload:
        return payload[canonical_key]
    for alias in aliases:
        if alias in payload:
            return payload[alias]
    return None


def normalize_report_obj(obj: Any) -> dict[str, Any]:
    payload: Any = obj
    if isinstance(payload, str):
        try:
            payload = _json_loads_with_nested_string(payload)
        except ValueError:
            payload = extract_first_json_object(payload)

    if not isinstance(payload, dict):
        raise ValueError("Report output is not a JSON object")

    headline_raw = _top_level_value(payload, "headline", ("title", "heading"))
    events_raw = _top_level_value(payload, "notable_events", ("events", "notable"))
    issues_raw = _top_level_value(payload, "current_issues", ("issues", "current"))
    recs_raw = _top_level_value(payload, "recommendations", ("recs", "actions"))

    notable_events: list[dict[str, Any]] = []
    for item in _coerce_list(events_raw):
        if isinstance(item, str):
            notable_events.append(
                {"time": None, "summary": item, "severity": "info"}
            )
            continue
        if isinstance(item, dict):
            summary = (
                item.get("summary")
                or item.get("text")
                or item.get("message")
                or ""
            )
            notable_events.append(
                {
                    "time": item.get("time") or item.get("ts"),
                    "summary": _coerce_text(summary),
                    "severity": _normalize_severity(
                        item.get("severity") or item.get("level")
                    ),
                }
            )
            continue
        notable_events.append(
            {"time": None, "summary": _coerce_text(item), "severity": "info"}
        )

    current_issues: list[dict[str, Any]] = []
    for item in _coerce_list(issues_raw):
        if isinstance(item, str):
            current_issues.append({"summary": item, "suggestion": ""})
            continue
        if isinstance(item, dict):
            summary = item.get("summary") or item.get("text") or item.get("issue") or ""
            suggestion = (
                item.get("suggestion")
                or item.get("recommendation")
                or item.get("action")
                or ""
            )
            current_issues.append(
                {
                    "summary": _coerce_text(summary),
                    "suggestion": _coerce_text(suggestion),
                }
            )
            continue
        current_issues.append({"summary": _coerce_text(item), "suggestion": ""})

    recommendations: list[str] = []
    for item in _coerce_list(recs_raw):
        if isinstance(item, str):
            recommendations.append(item)
            continue
        if isinstance(item, dict):
            text = (
                item.get("text")
                or item.get("recommendation")
                or item.get("suggestion")
                or item.get("summary")
                or ""
            )
            if text:
                recommendations.append(_coerce_text(text))
            continue
        recommendations.append(_coerce_text(item))

    return {
        "headline": _coerce_text(headline_raw, default="Ops Report") or "Ops Report",
        "notable_events": notable_events,
        "current_issues": current_issues,
        "recommendations": recommendations,
    }


def sanity_check_report_dict(payload: dict[str, Any]) -> dict[str, Any]:
    # Deterministic caps: headline over limit is rejected; list/string fields are truncated.
    headline = _coerce_text(payload.get("headline"), default="Ops Report")
    if len(headline) > MAX_HEADLINE_LEN:
        raise ValueError("Report headline too long")

    notable_events = _coerce_list(payload.get("notable_events"))[:MAX_ITEMS]
    current_issues = _coerce_list(payload.get("current_issues"))[:MAX_ITEMS]
    recommendations = _coerce_list(payload.get("recommendations"))[:MAX_ITEMS]

    sanitized_events: list[dict[str, Any]] = []
    for item in notable_events:
        if not isinstance(item, dict):
            continue
        sanitized_events.append(
            {
                "time": _coerce_text(item.get("time"), default="")[:MAX_TEXT_LEN] or None,
                "summary": _coerce_text(item.get("summary"), default="")[:MAX_TEXT_LEN],
                "severity": _normalize_severity(item.get("severity")),
            }
        )

    sanitized_issues: list[dict[str, Any]] = []
    for item in current_issues:
        if not isinstance(item, dict):
            continue
        sanitized_issues.append(
            {
                "summary": _coerce_text(item.get("summary"), default="")[:MAX_TEXT_LEN],
                "suggestion": _coerce_text(item.get("suggestion"), default="")[
                    :MAX_TEXT_LEN
                ],
            }
        )

    sanitized_recommendations = [
        _coerce_text(item, default="")[:MAX_TEXT_LEN] for item in recommendations
    ]
    sanitized_recommendations = [item for item in sanitized_recommendations if item]

    return {
        "headline": headline,
        "notable_events": sanitized_events,
        "current_issues": sanitized_issues,
        "recommendations": sanitized_recommendations,
    }


def normalize_report(obj: Any) -> ReportData:
    normalized = normalize_report_obj(obj)
    sane = sanity_check_report_dict(normalized)
    try:
        return ReportData.model_validate(sane)
    except ValidationError as exc:
        raise ValueError("Model JSON does not match report schema") from exc


def parse_report_data(raw_text: str) -> ReportData:
    return normalize_report(raw_text)


def validate_report_data(report_data: ReportData) -> tuple[bool, str | None]:
    headline = (report_data.headline or "").strip()
    if not headline:
        return False, "headline is empty"

    has_recommendation = any((item or "").strip() for item in report_data.recommendations)
    has_current_issue = any((issue.summary or "").strip() for issue in report_data.current_issues)
    has_notable_event = any((event.summary or "").strip() for event in report_data.notable_events)

    if has_recommendation or has_current_issue or has_notable_event:
        return True, None
    return (
        False,
        "missing actionable content (recommendations/current_issues/notable_events summaries)",
    )


def render_report_markdown(
    *,
    report_data: ReportData,
    generated_at: str,
    range_minutes: int,
    status_summary: dict[str, Any],
    sources_info: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# Ops Report ({generated_at})")
    lines.append("")
    lines.append(f"**Overall:** {report_data.headline}")
    lines.append("")
    lines.append("## Current status")
    lines.append(f"- Window: last {range_minutes} minutes")
    lines.append(
        f"- Checks: total={status_summary.get('total', 0)}, up={status_summary.get('up', 0)}, "
        f"down={status_summary.get('down', 0)}, unknown={status_summary.get('unknown', 0)}"
    )
    down_checks = status_summary.get("down_checks")
    if isinstance(down_checks, list) and down_checks:
        down_ids = [item.get("id") for item in down_checks if isinstance(item, dict) and item.get("id")]
        if down_ids:
            lines.append(f"- Down checks: {', '.join(down_ids)}")
    lines.append("")
    lines.append("## Notable events")
    if report_data.notable_events:
        for event in report_data.notable_events:
            event_time = event.time or "unknown"
            lines.append(f"- [{event.severity}] {event_time} - {event.summary}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Current issues")
    if report_data.current_issues:
        for issue in report_data.current_issues:
            lines.append(f"- {issue.summary} (suggestion: {issue.suggestion})")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Recommendations")
    if report_data.recommendations:
        for idx, recommendation in enumerate(report_data.recommendations, start=1):
            lines.append(f"{idx}. {recommendation}")
    else:
        lines.append("1. None")
    lines.append("")
    lines.append("## Sources")
    lines.append(f"- ops_summary: {'yes' if sources_info.get('ops_summary_included') else 'no'}")
    lines.append(f"- status_summary: {'yes' if sources_info.get('status_summary_included') else 'no'}")
    lines.append(f"- events_limit: {sources_info.get('events_limit', 0)}")
    lines.append(f"- proxmox: {'yes' if sources_info.get('proxmox_included') else 'no'}")
    return "\n".join(lines)


def proxmox_payload_from_cache(*, proxmox_cache: Any) -> dict[str, Any]:
    payload = proxmox_cache.last_payload if isinstance(proxmox_cache.last_payload, dict) else {}
    return {
        "last_payload": payload,
        "last_fetch_ts": serialize_ts(getattr(proxmox_cache, "last_fetch_ts", None)),
        "last_error": getattr(proxmox_cache, "last_error", None),
    }


def build_fallback_report_data(*, error_text: str) -> ReportData:
    return ReportData.model_validate(
        {
            "headline": "Ops Report",
            "notable_events": [],
            "current_issues": [
                {
                    "summary": "LLM report generation failed",
                    "suggestion": error_text,
                }
            ],
            "recommendations": [],
        }
    )
