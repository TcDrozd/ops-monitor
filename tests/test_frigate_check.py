import unittest
from unittest.mock import Mock, patch

import requests

from app.checks.frigate_check import RECORDING_STORAGE_PATH, run_frigate


NOW = 2_000_000_000


def response(status_code: int, payload) -> Mock:
    result = Mock(status_code=status_code)
    if isinstance(payload, Exception):
        result.json.side_effect = payload
    else:
        result.json.return_value = payload
    return result


def stats_payload(
    *, total_mb: float = 2_000_000, pid: int | None = 4321, uptime: int = 300
) -> dict:
    recording_process = {} if pid is None else {"pid": pid}
    return {
        "service": {
            "uptime": uptime,
            "storage": {RECORDING_STORAGE_PATH: {"total": total_mb}},
        },
        "processes": {"recording": recording_process},
    }


class FrigateCheckTests(unittest.TestCase):
    def test_healthy_checks_stats_and_fresh_recordings_with_explicit_window(self) -> None:
        cameras = ["FrontNorth", "Back Yard"]

        def get(url, **kwargs):
            if url.endswith("/api/stats"):
                self.assertNotIn("params", kwargs)
                return response(200, stats_payload())
            return response(
                200,
                [{"start_time": NOW - 15, "end_time": NOW - 5}],
            )

        with patch("app.checks.frigate_check.time.time", return_value=NOW), patch(
            "app.checks.frigate_check.requests.get", side_effect=get
        ) as mock_get:
            result = run_frigate(
                "http://frigate.local:5000/",
                cameras,
                timeout_s=3,
                max_recording_age_s=120,
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.error)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(
            mock_get.call_args_list[1].args[0],
            "http://frigate.local:5000/api/FrontNorth/recordings",
        )
        self.assertEqual(
            mock_get.call_args_list[2].args[0],
            "http://frigate.local:5000/api/Back%20Yard/recordings",
        )
        for call in mock_get.call_args_list[1:]:
            self.assertEqual(
                call.kwargs["params"],
                {"after": NOW - 120, "before": NOW},
            )
            self.assertEqual(call.kwargs["timeout"], (3, 3))

    def test_root_volume_fallback_reports_storage_total(self) -> None:
        with patch(
            "app.checks.frigate_check.requests.get",
            return_value=response(200, stats_payload(total_mb=250_000)),
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
            )

        self.assertFalse(result.ok)
        self.assertIn(RECORDING_STORAGE_PATH, result.error)
        self.assertIn("250000 MB", result.error)
        self.assertIn("1500000 MB", result.error)
        self.assertIn("root-volume fallback", result.error)

    def test_missing_recording_manager_pid_fails(self) -> None:
        with patch(
            "app.checks.frigate_check.requests.get",
            return_value=response(200, stats_payload(pid=None)),
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
            )

        self.assertFalse(result.ok)
        self.assertEqual(
            result.error,
            "recording-manager PID missing from /api/stats "
            "(processes.recording.pid)",
        )

    def test_stale_and_missing_cameras_are_listed(self) -> None:
        replies = [
            response(200, stats_payload()),
            response(200, [{"end_time": NOW - 180}]),
            response(200, []),
            response(200, [{"end_time": NOW - 10}]),
        ]
        with patch("app.checks.frigate_check.time.time", return_value=NOW), patch(
            "app.checks.frigate_check.requests.get", side_effect=replies
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth", "DogwoodCorner", "Driveway"],
                timeout_s=3,
                max_recording_age_s=120,
            )

        self.assertFalse(result.ok)
        self.assertIn("missing recording segments: DogwoodCorner", result.error)
        self.assertIn("stale recording segments: FrontNorth (180s old)", result.error)
        self.assertNotIn("Driveway", result.error)

    def test_startup_grace_skips_only_camera_freshness(self) -> None:
        with patch(
            "app.checks.frigate_check.requests.get",
            return_value=response(200, stats_payload(uptime=119)),
        ) as mock_get:
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
                startup_grace_s=120,
            )

        self.assertTrue(result.ok)
        mock_get.assert_called_once_with(
            "http://frigate.local:5000/api/stats", timeout=(3, 3)
        )

    def test_startup_grace_still_enforces_storage_and_pid(self) -> None:
        payload = stats_payload(total_mb=100_000, pid=None, uptime=10)
        with patch(
            "app.checks.frigate_check.requests.get",
            return_value=response(200, payload),
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
            )

        self.assertFalse(result.ok)
        self.assertIn("root-volume fallback", result.error)
        self.assertIn("recording-manager PID missing", result.error)

    def test_api_connection_failure_returns_check_result(self) -> None:
        with patch(
            "app.checks.frigate_check.requests.get",
            side_effect=requests.ConnectionError("connection refused"),
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
            )

        self.assertFalse(result.ok)
        self.assertIsNone(result.status_code)
        self.assertIn("Frigate API unreachable", result.error)
        self.assertIn("connection refused", result.error)

    def test_camera_api_failure_identifies_camera(self) -> None:
        replies = [response(200, stats_payload()), response(503, {})]
        with patch("app.checks.frigate_check.time.time", return_value=NOW), patch(
            "app.checks.frigate_check.requests.get", side_effect=replies
        ):
            result = run_frigate(
                "http://frigate.local:5000",
                ["FrontNorth"],
                timeout_s=3,
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(
            result.error, "recordings API failures: FrontNorth (HTTP 503)"
        )


if __name__ == "__main__":
    unittest.main()
