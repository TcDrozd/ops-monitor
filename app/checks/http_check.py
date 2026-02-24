from __future__ import annotations

import time
import requests

from app.checks.results import CheckResult


def run_http(url: str, timeout_s: int, connect_timeout_s: float | None = None) -> CheckResult:
    start = time.perf_counter()
    try:
        connect_timeout = timeout_s if connect_timeout_s is None else connect_timeout_s
        r = requests.get(url, timeout=(connect_timeout, timeout_s))
        latency_ms = int((time.perf_counter() - start) * 1000)
        ok = 200 <= r.status_code < 300
        return CheckResult(ok=ok, latency_ms=latency_ms, status_code=r.status_code)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(ok=False, latency_ms=latency_ms, error=str(e))
