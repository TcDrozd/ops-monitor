from __future__ import annotations

from pathlib import Path
import sqlite3
import threading
from typing import Any


class SQLitePersistence:
    def __init__(self, db_path: str, max_events: int = 500) -> None:
        self._db_path = self._resolve_db_path(db_path)
        self._max_events = max_events
        self._lock = threading.Lock()

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._init_schema()

    @staticmethod
    def _resolve_db_path(raw_path: str) -> Path:
        p = Path(raw_path).expanduser()
        if p.is_absolute():
            return p
        return Path.cwd() / p

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS check_states (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                ok INTEGER,
                fail_count INTEGER NOT NULL DEFAULT 0,
                down_threshold INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                last_ok TEXT,
                last_change TEXT,
                latency_ms INTEGER,
                status_code INTEGER,
                error TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                check_id TEXT NOT NULL,
                event TEXT NOT NULL,
                ok INTEGER,
                latency_ms INTEGER,
                status_code INTEGER,
                error TEXT
            )
            """
        )
        self._add_column_if_missing(
            table="check_states",
            column="fail_count",
            ddl="INTEGER NOT NULL DEFAULT 0",
        )
        self._add_column_if_missing(
            table="check_states",
            column="down_threshold",
            ddl="INTEGER NOT NULL DEFAULT 1",
        )
        self._conn.commit()

    def _add_column_if_missing(self, table: str, column: str, ddl: str) -> None:
        cols = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row["name"] for row in cols}
        if column in existing:
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    @staticmethod
    def _to_db_bool(v: bool | None) -> int | None:
        if v is None:
            return None
        return 1 if v else 0

    @staticmethod
    def _from_db_bool(v: Any) -> bool | None:
        if v is None:
            return None
        return bool(v)

    def upsert_check_state(self, check_state: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO check_states (
                    id, type, ok, fail_count, down_threshold, last_run, last_ok, last_change,
                    latency_ms, status_code, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type=excluded.type,
                    ok=excluded.ok,
                    fail_count=excluded.fail_count,
                    down_threshold=excluded.down_threshold,
                    last_run=excluded.last_run,
                    last_ok=excluded.last_ok,
                    last_change=excluded.last_change,
                    latency_ms=excluded.latency_ms,
                    status_code=excluded.status_code,
                    error=excluded.error
                """,
                (
                    check_state["id"],
                    check_state["type"],
                    self._to_db_bool(check_state.get("ok")),
                    check_state.get("fail_count", 0),
                    check_state.get("down_threshold", 1),
                    check_state.get("last_run"),
                    check_state.get("last_ok"),
                    check_state.get("last_change"),
                    check_state.get("latency_ms"),
                    check_state.get("status_code"),
                    check_state.get("error"),
                ),
            )
            self._conn.commit()

    def insert_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO events (
                    ts, check_id, event, ok, latency_ms, status_code, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["ts"],
                    event["id"],
                    event["event"],
                    self._to_db_bool(event.get("ok")),
                    event.get("latency_ms"),
                    event.get("status_code"),
                    event.get("error"),
                ),
            )
            self._trim_events_locked()
            self._conn.commit()

    def _trim_events_locked(self) -> None:
        self._conn.execute(
            """
            DELETE FROM events
            WHERE row_id NOT IN (
                SELECT row_id FROM events ORDER BY row_id DESC LIMIT ?
            )
            """,
            (self._max_events,),
        )

    def load_all_check_states(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, type, ok, last_run, last_ok, last_change,
                       fail_count, down_threshold, latency_ms, status_code, error
                FROM check_states
                """
            ).fetchall()

        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            out[r["id"]] = {
                "id": r["id"],
                "type": r["type"],
                "ok": self._from_db_bool(r["ok"]),
                "fail_count": r["fail_count"] if r["fail_count"] is not None else 0,
                "down_threshold": (
                    r["down_threshold"] if r["down_threshold"] is not None else 1
                ),
                "last_run": r["last_run"],
                "last_ok": r["last_ok"],
                "last_change": r["last_change"],
                "latency_ms": r["latency_ms"],
                "status_code": r["status_code"],
                "error": r["error"],
            }
        return out

    def load_recent_events(self, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT ts, check_id, event, ok, latency_ms, status_code, error
                FROM events
                ORDER BY row_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        events = [
            {
                "ts": r["ts"],
                "id": r["check_id"],
                "event": r["event"],
                "ok": self._from_db_bool(r["ok"]),
                "latency_ms": r["latency_ms"],
                "status_code": r["status_code"],
                "error": r["error"],
            }
            for r in rows
        ]
        # StateStore keeps events oldest->newest and reverses on read.
        events.reverse()
        return events

    def close(self) -> None:
        with self._lock:
            self._conn.close()
