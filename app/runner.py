from __future__ import annotations

import time
from app.registry import load_registry, apply_defaults
from app.state import StateStore
from app.checks.http_check import run_http
from app.checks.tcp_check import run_tcp

def run_once(store: StateStore) -> None:
    reg = load_registry()
    checks = apply_defaults(reg)

    for check_id, c in checks.items():
        store.ensure_check(check_id, c["type"])

    for check_id, c in checks.items():
        timeout_s = int(c["timeout_s"])

        if c["type"] == "http":
            res = run_http(c["url"], timeout_s=timeout_s)
            store.update(
                check_id,
                ok=res.ok,
                latency_ms=res.latency_ms,
                status_code=res.status_code,
                error=res.error,
            )

        elif c["type"] == "tcp":
            res = run_tcp(c["host"], c["port"], timeout_s=timeout_s)
            store.update(
                check_id,
                ok=res.ok,
                latency_ms=res.latency_ms,
                error=res.error,
            )

def loop_forever(store: StateStore, interval_s: int) -> None:
    while True:
        start = time.perf_counter()
        run_once(store)
        elapsed = time.perf_counter() - start
        sleep_s = max(0.0, interval_s - elapsed)
        time.sleep(sleep_s)
