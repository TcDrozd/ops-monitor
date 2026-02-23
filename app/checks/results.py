from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    ok: bool
    latency_ms: int
    status_code: int | None = None
    error: str | None = None
