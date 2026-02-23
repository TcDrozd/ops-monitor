from __future__ import annotations

from typing import Any, Dict


def format_transition(
    event: Dict[str, Any], check: Dict[str, Any], state: Dict[str, Any]
) -> tuple[str, str]:
    # Title
    status = event["event"]  # "UP" or "DOWN"
    title = f"[{status}] {check['id']}"

    # Target
    if check["type"] == "http":
        target = check["url"]
    else:
        target = f"{check['host']}:{check['port']}"

    # Body
    lines = [
        f"Check: {check['id']} ({check['type']})",
        f"Target: {target}",
        f"Latency: {state.get('latency_ms')} ms",
    ]
    if state.get("status_code") is not None:
        lines.append(f"HTTP: {state.get('status_code')}")
    if state.get("error"):
        lines.append(f"Error: {state['error']}")
    lines.append(f"Time: {event['ts']}")
    return title, "\n".join(lines)
