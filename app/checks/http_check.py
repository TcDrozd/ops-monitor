from __future__ import annotations

import time
from dataclasses import dataclass
import requests

@dataclass
class CheckResult:
    ok: bool
    latency_ms: int
    status_code: int | None = None
    error: str | None = None

def run_http(url: str, timeout_s: int) -> CheckResult:
    start = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout_s)
        latency_ms = int((time.perf_counter() - start) * 1000)
        ok = 200 <= r.status_code < 300
        return CheckResult(ok=ok, latency_ms=latency_ms, status_code=r.status_code)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(ok=False, latency_ms=latency_ms, error=str(e))
