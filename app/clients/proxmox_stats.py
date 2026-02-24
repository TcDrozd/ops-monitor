from __future__ import annotations

from urllib.parse import urlparse

import requests

from app.config import settings


def _build_summary_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.path and parsed.path != "/":
        return base_url
    return f"{base_url.rstrip('/')}/api/metrics/health-summary"


def get_health_summary() -> dict:
    base_url = settings.PROXMOX_STATS_BASE_URL
    if not base_url:
        return {
            "status": "unavailable",
            "error": "PROXMOX_STATS_BASE_URL is not configured",
        }

    try:
        resp = requests.get(
            _build_summary_url(base_url),
            timeout=settings.PROXMOX_STATS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}

    if resp.status_code >= 400:
        return {
            "status": "unavailable",
            "error": f"proxmox-stats returned HTTP {resp.status_code}",
        }

    try:
        payload = resp.json()
    except ValueError as exc:
        return {"status": "unavailable", "error": f"invalid JSON: {exc}"}

    if isinstance(payload, dict):
        return payload

    return {"status": "unknown", "error": "proxmox-stats payload is not a JSON object"}
