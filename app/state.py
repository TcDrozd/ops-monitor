from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.persistence import SQLitePersistence


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
    def __init__(self, db_path: str | None = None, max_events: int = 500) -> None:
        self._checks: dict[str, CheckState] = {}
        self._events: list[dict[str, Any]] = []
        self._max_events = max_events
        self._lock = threading.Lock()
        self._persistence = (
            SQLitePersistence(db_path, max_events=max_events) if db_path else None
        )

        if self._persistence:
            self._load_from_db()

    def _load_from_db(self) -> None:
        assert self._persistence is not None

        persisted = self._persistence.load_all_check_states()
        self._checks = {
            check_id: CheckState(**state_dict)
            for check_id, state_dict in persisted.items()
        }
        self._events = self._persistence.load_recent_events(self._max_events)

    def _build_event(
        self,
        ts: str,
        check_id: str,
        event_name: str,
        ok: bool,
        latency_ms: int,
        status_code: int | None,
        error: str | None,
    ) -> dict[str, Any]:
        return {
            "ts": ts,
            "id": check_id,
            "event": event_name,
            "ok": ok,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "error": error,
        }

    def ensure_check(self, check_id: str, check_type: str) -> None:
        with self._lock:
            if check_id not in self._checks:
                cs = CheckState(id=check_id, type=check_type)
                self._checks[check_id] = cs
                if self._persistence:
                    self._persistence.upsert_check_state(cs.to_dict())

    def update(
        self,
        check_id: str,
        ok: bool,
        latency_ms: int,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            cs = self._checks[check_id]
            prev_ok = cs.ok

            cs.ok = ok
            cs.last_run = now_iso()
            cs.latency_ms = latency_ms
            cs.status_code = status_code
            cs.error = error

            if ok:
                cs.last_ok = cs.last_run

            event: dict[str, Any] | None = None
            if prev_ok is None:
                cs.last_change = cs.last_run
                event = self._build_event(
                    ts=cs.last_run,
                    check_id=check_id,
                    event_name="INIT",
                    ok=ok,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    error=error,
                )
            elif prev_ok != ok:
                cs.last_change = cs.last_run
                event = self._build_event(
                    ts=cs.last_run,
                    check_id=check_id,
                    event_name="UP" if ok else "DOWN",
                    ok=ok,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    error=error,
                )

            if event is not None:
                self._events.append(event)
                if self._persistence:
                    self._persistence.insert_event(event)

            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]

            if self._persistence:
                self._persistence.upsert_check_state(cs.to_dict())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._checks.items()}

    def summary(self) -> dict[str, Any]:
        snap = self.snapshot()
        total = len(snap)
        up = sum(1 for v in snap.values() if v["ok"] is True)
        down = sum(1 for v in snap.values() if v["ok"] is False)
        unknown = sum(1 for v in snap.values() if v["ok"] is None)
        down_checks = [v for v in snap.values() if v["ok"] is False]

        return {
            "total": total,
            "up": up,
            "down": down,
            "unknown": unknown,
            "down_checks": down_checks,
        }

    def events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._events[-limit:]))
