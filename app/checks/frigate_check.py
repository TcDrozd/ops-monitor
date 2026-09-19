from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import requests

from app.checks.results import CheckResult


RECORDING_STORAGE_PATH = "/media/frigate/recordings"


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _request_timeout(
    timeout_s: int, connect_timeout_s: float | None
) -> tuple[float, int]:
    connect_timeout = timeout_s if connect_timeout_s is None else connect_timeout_s
    return connect_timeout, timeout_s


def _json_object(response: requests.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


def run_frigate(
    base_url: str,
    required_cameras: Sequence[str],
    timeout_s: int,
    min_recording_storage_mb: float = 1_500_000,
    max_recording_age_s: int = 120,
    startup_grace_s: int = 120,
    connect_timeout_s: float | None = None,
) -> CheckResult:
    """Run Frigate's composite API, storage, process, and recording check."""
    start = time.perf_counter()
    api_base = str(base_url).rstrip("/")
    stats_url = f"{api_base}/api/stats"
    timeout = _request_timeout(timeout_s, connect_timeout_s)

    try:
        stats_response = requests.get(stats_url, timeout=timeout)
    except requests.RequestException as exc:
        return CheckResult(
            ok=False,
            latency_ms=_latency_ms(start),
            error=f"Frigate API unreachable at {stats_url}: {exc}",
        )

    if not 200 <= stats_response.status_code < 300:
        return CheckResult(
            ok=False,
            latency_ms=_latency_ms(start),
            status_code=stats_response.status_code,
            error=f"Frigate API /api/stats returned HTTP {stats_response.status_code}",
        )

    stats = _json_object(stats_response)
    if stats is None:
        return CheckResult(
            ok=False,
            latency_ms=_latency_ms(start),
            status_code=stats_response.status_code,
            error="Frigate API /api/stats returned invalid JSON object",
        )

    failures: list[str] = []
    service = stats.get("service")
    service = service if isinstance(service, dict) else {}
    storage = service.get("storage", {})
    recording_storage = (
        storage.get(RECORDING_STORAGE_PATH) if isinstance(storage, dict) else None
    )
    total_mb = (
        recording_storage.get("total")
        if isinstance(recording_storage, dict)
        else None
    )
    if not isinstance(total_mb, (int, float)) or isinstance(total_mb, bool):
        failures.append(
            f"recording storage {RECORDING_STORAGE_PATH} total is missing or invalid; "
            "possible root-volume fallback"
        )
    elif total_mb < min_recording_storage_mb:
        failures.append(
            f"recording storage {RECORDING_STORAGE_PATH} total "
            f"{_format_number(float(total_mb))} MB is below minimum "
            f"{_format_number(float(min_recording_storage_mb))} MB; "
            "possible root-volume fallback"
        )

    processes = stats.get("processes", {})
    recording_process = (
        processes.get("recording") if isinstance(processes, dict) else None
    )
    recording_pid = (
        recording_process.get("pid")
        if isinstance(recording_process, dict)
        else None
    )
    if (
        not isinstance(recording_pid, int)
        or isinstance(recording_pid, bool)
        or recording_pid <= 0
    ):
        failures.append(
            "recording-manager PID missing from /api/stats "
            "(processes.recording.pid)"
        )

    if failures:
        return CheckResult(
            ok=False,
            latency_ms=_latency_ms(start),
            status_code=stats_response.status_code,
            error="; ".join(failures),
        )

    uptime = service.get("uptime")
    in_startup_grace = (
        isinstance(uptime, (int, float))
        and not isinstance(uptime, bool)
        and uptime < startup_grace_s
    )
    if in_startup_grace:
        return CheckResult(
            ok=True,
            latency_ms=_latency_ms(start),
            status_code=stats_response.status_code,
        )

    before = int(time.time())
    after = before - max_recording_age_s
    missing_cameras: list[str] = []
    stale_cameras: list[str] = []
    camera_api_failures: list[str] = []
    camera_failure_status: int | None = None

    for camera in required_cameras:
        camera_url = f"{api_base}/api/{quote(camera, safe='')}/recordings"
        try:
            response = requests.get(
                camera_url,
                params={"after": after, "before": before},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            camera_api_failures.append(f"{camera} ({exc})")
            continue

        if not 200 <= response.status_code < 300:
            camera_failure_status = camera_failure_status or response.status_code
            camera_api_failures.append(f"{camera} (HTTP {response.status_code})")
            continue

        try:
            recordings = response.json()
        except ValueError:
            camera_api_failures.append(f"{camera} (invalid JSON)")
            continue

        if not isinstance(recordings, list) or not recordings:
            missing_cameras.append(camera)
            continue

        end_times = [
            recording.get("end_time")
            for recording in recordings
            if isinstance(recording, dict)
            and isinstance(recording.get("end_time"), (int, float))
            and not isinstance(recording.get("end_time"), bool)
        ]
        if not end_times:
            missing_cameras.append(camera)
            continue

        latest_end = max(end_times)
        if latest_end < after:
            stale_cameras.append(
                f"{camera} ({max(0, int(before - latest_end))}s old)"
            )

    recording_failures: list[str] = []
    if camera_api_failures:
        recording_failures.append(
            "recordings API failures: " + ", ".join(camera_api_failures)
        )
    if missing_cameras:
        recording_failures.append(
            "missing recording segments: " + ", ".join(missing_cameras)
        )
    if stale_cameras:
        recording_failures.append(
            "stale recording segments: " + ", ".join(stale_cameras)
        )

    if recording_failures:
        return CheckResult(
            ok=False,
            latency_ms=_latency_ms(start),
            status_code=camera_failure_status or stats_response.status_code,
            error="; ".join(recording_failures),
        )

    return CheckResult(
        ok=True,
        latency_ms=_latency_ms(start),
        status_code=stats_response.status_code,
    )
