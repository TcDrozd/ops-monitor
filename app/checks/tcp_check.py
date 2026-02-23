from __future__ import annotations

import socket
import time
from dataclasses import dataclass

@dataclass
class CheckResult:
    ok: bool
    latency_ms: int
    error: str | None = None

def run_tcp(host: str, port: int, timeout_s: int) -> CheckResult:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            latency_ms = int((time.perf_counter() - start) * 1000)
            return CheckResult(ok=True, latency_ms=latency_ms)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(ok=False, latency_ms=latency_ms, error=str(e))
