from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class CheckState:
    id: str
    type: str
    ok: bool | None = None
    last_run: str | None = None
    last_ok: str | None = None
    last_change: str | None = None
    latency_ms: int | None = None
    status_code: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class StateStore:
    def __init__(self) -> None:
        self._checks: dict[str, CheckState] = {}
        self._events: list[dict[str, Any]] = []

    def ensure_check(self, check_id: str, check_type: str) -> None:
        if check_id not in self._checks:
            self._checks[check_id] = CheckState(id=check_id, type=check_type)

    def update(
        self,
        check_id: str,
        ok: bool,
        latency_ms: int,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        cs = self._checks[check_id]
        prev_ok = cs.ok

        cs.ok = ok
        cs.last_run = now_iso()
        cs.latency_ms = latency_ms
        cs.status_code = status_code
        cs.error = error

        if ok:
            cs.last_ok = cs.last_run

        if prev_ok is None:
            cs.last_change = cs.last_run
            self._events.append({
                "ts": cs.last_run,
                "id": check_id,
                "event": "INIT",
                "ok": ok,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "error": error,
            })
        elif prev_ok != ok:
            cs.last_change = cs.last_run
            self._events.append({
                "ts": cs.last_run,
                "id": check_id,
                "event": "UP" if ok else "DOWN",
                "ok": ok,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "error": error,
            })

        # keep events bounded
        if len(self._events) > 500:
            self._events = self._events[-500:]

    def snapshot(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in self._checks.items()}

    def events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._events[-limit:]))
