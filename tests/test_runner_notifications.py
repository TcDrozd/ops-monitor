import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.checks.results import CheckResult
from app.runner import run_once
from app.state import StateStore


class RunnerNotificationTests(unittest.TestCase):
    def test_notifies_on_down_and_up_transitions_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "runner-notify.sqlite3")
            store = StateStore(db_path=db_path)
            notifier = Mock()

            checks = {
                "rory-walk": {
                    "id": "rory-walk",
                    "type": "http",
                    "url": "http://example.local/health",
                    "timeout_s": 2,
                }
            }

            with patch("app.runner.load_registry", return_value=object()), patch(
                "app.runner.apply_defaults", return_value=checks
            ), patch(
                "app.runner.run_http", return_value=CheckResult(ok=False, latency_ms=10, status_code=503)
            ):
                run_once(store, notifier=notifier)

            notifier.send_down.assert_not_called()  # INIT only
            notifier.send_up.assert_not_called()

            with patch("app.runner.load_registry", return_value=object()), patch(
                "app.runner.apply_defaults", return_value=checks
            ), patch(
                "app.runner.run_http", return_value=CheckResult(ok=False, latency_ms=8, status_code=503)
            ):
                run_once(store, notifier=notifier)

            notifier.send_down.assert_not_called()  # still down, no transition
            notifier.send_up.assert_not_called()

            with patch("app.runner.load_registry", return_value=object()), patch(
                "app.runner.apply_defaults", return_value=checks
            ), patch(
                "app.runner.run_http", return_value=CheckResult(ok=True, latency_ms=5, status_code=200)
            ):
                run_once(store, notifier=notifier)

            notifier.send_up.assert_called_once()

            with patch("app.runner.load_registry", return_value=object()), patch(
                "app.runner.apply_defaults", return_value=checks
            ), patch(
                "app.runner.run_http", return_value=CheckResult(ok=False, latency_ms=12, status_code=503, error="down")
            ):
                run_once(store, notifier=notifier)

            notifier.send_down.assert_called_once()


if __name__ == "__main__":
    unittest.main()
