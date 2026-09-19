import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.checks.results import CheckResult
from app.runner import run_once
from app.state import StateStore


CHECK = {
    "id": "frigate",
    "type": "frigate",
    "base_url": "http://frigate.local:5000",
    "required_cameras": ["FrontNorth", "Driveway"],
    "min_fresh_cameras": 2,
    "min_recording_storage_mb": 1_500_000,
    "max_recording_age_s": 120,
    "startup_grace_s": 120,
    "timeout_s": 4,
    "down_threshold": 2,
}


class RunnerFrigateTests(unittest.TestCase):
    def _run(self, store: StateStore, result: CheckResult, notifier=None) -> Mock:
        with patch(
            "app.runner.get_health_summary",
            return_value={"status": "unavailable", "error": "disabled in test"},
        ), patch("app.runner.load_registry", return_value=object()), patch(
            "app.runner.apply_defaults", return_value={"frigate": CHECK}
        ), patch("app.runner.run_frigate", return_value=result) as run_frigate:
            run_once(store, notifier=notifier)
        return run_frigate

    def test_runner_dispatches_dedicated_frigate_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "runner.sqlite3"))
            run_frigate = self._run(
                store, CheckResult(ok=True, latency_ms=9, status_code=200)
            )

        run_frigate.assert_called_once_with(
            base_url="http://frigate.local:5000",
            required_cameras=["FrontNorth", "Driveway"],
            timeout_s=4,
            min_fresh_cameras=2,
            min_recording_storage_mb=1_500_000.0,
            max_recording_age_s=120,
            startup_grace_s=120,
            connect_timeout_s=None,
        )

    def test_down_transition_is_debounced_and_recovery_is_immediate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "transitions.sqlite3"))
            notifier = Mock()

            self._run(
                store,
                CheckResult(ok=True, latency_ms=5, status_code=200),
                notifier,
            )
            self._run(
                store,
                CheckResult(ok=False, latency_ms=5, status_code=200, error="stale"),
                notifier,
            )
            self.assertTrue(store.check_state("frigate")["ok"])
            notifier.send_down.assert_not_called()

            self._run(
                store,
                CheckResult(ok=False, latency_ms=5, status_code=200, error="stale"),
                notifier,
            )
            self.assertFalse(store.check_state("frigate")["ok"])
            notifier.send_down.assert_called_once()

            self._run(
                store,
                CheckResult(ok=True, latency_ms=5, status_code=200),
                notifier,
            )
            self.assertTrue(store.check_state("frigate")["ok"])
            self.assertEqual(store.check_state("frigate")["fail_count"], 0)
            notifier.send_up.assert_called_once()


if __name__ == "__main__":
    unittest.main()
