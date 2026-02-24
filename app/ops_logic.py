from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def serialize_ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def utcnow_iso() -> str:
    return serialize_ts(datetime.now(timezone.utc)) or ""


def compute_overall_status(
    core_down: bool,
    non_core_down: bool,
    proxmox_status: str,
) -> str:
    if core_down:
        return "crit"
    if proxmox_status == "warn" or non_core_down:
        return "warn"
    return "ok"


def summarize_checks(
    check_results: dict[str, dict[str, Any]],
    core_check_ids: set[str],
) -> tuple[int, int, list[str], bool, bool]:
    up = 0
    down = 0
    down_list: list[str] = []
    core_down = False
    non_core_down = False

    for check_id, state in check_results.items():
        ok = state.get("ok")
        if ok is True:
            up += 1
        elif ok is False:
            down += 1
            down_list.append(check_id)
            if check_id in core_check_ids:
                core_down = True
            else:
                non_core_down = True

    return up, down, down_list, core_down, non_core_down
