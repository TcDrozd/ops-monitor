from __future__ import annotations

import time

from app.checks.http_check import run_http
from app.checks.tcp_check import run_tcp
from app.checks.results import CheckResult
from app.config import settings
from app.formatting import format_transition
from app.notifier import NtfyConfig, NtfyNotifier
from app.registry import apply_defaults, load_registry
from app.state import StateStore


def _notify_transition(
    notifier: NtfyNotifier | None,
    event: dict | None,
    check: dict,
    state: dict,
) -> None:
    if notifier is None or event is None:
        return
    if event["event"] not in {"UP", "DOWN"}:
        return

    title, message = format_transition(event=event, check=check, state=state)
    try:
        if event["event"] == "DOWN":
            notifier.send_down(title=title, message=message)
        else:
            notifier.send_up(title=title, message=message)
    except Exception:
        # Notification errors should never stop the check loop.
        return


def _update_store_from_result(
    store: StateStore,
    check_id: str,
    check: dict,
    res: CheckResult,
    notifier: NtfyNotifier | None,
) -> None:
    event = store.update(
        check_id,
        ok=res.ok,
        latency_ms=res.latency_ms,
        status_code=res.status_code,
        error=res.error,
    )
    _notify_transition(notifier, event, check, store.check_state(check_id))


def build_notifier() -> NtfyNotifier | None:
    if not settings.NTFY_URL or not settings.NTFY_TOPIC:
        return None
    return NtfyNotifier(NtfyConfig(base_url=settings.NTFY_URL, topic=settings.NTFY_TOPIC))


def run_once(store: StateStore, notifier: NtfyNotifier | None = None) -> None:
    reg = load_registry()
    checks = apply_defaults(reg)

    for check_id, c in checks.items():
        store.ensure_check(check_id, c["type"])

    for check_id, c in checks.items():
        timeout_s = int(c["timeout_s"])

        if c["type"] == "http":
            res = run_http(c["url"], timeout_s=timeout_s)
            _update_store_from_result(store, check_id, c, res, notifier)
        elif c["type"] == "tcp":
            res = run_tcp(c["host"], c["port"], timeout_s=timeout_s)
            _update_store_from_result(store, check_id, c, res, notifier)


def loop_forever(store: StateStore, interval_s: int) -> None:
    notifier = build_notifier()
    while True:
        start = time.perf_counter()
        run_once(store, notifier=notifier)
        elapsed = time.perf_counter() - start
        sleep_s = max(0.0, interval_s - elapsed)
        time.sleep(sleep_s)
