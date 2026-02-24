import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.checks.http_check import run_http
from app.checks.results import CheckResult
from app.runner import _connect_timeout_override, run_once
from app.state import StateStore


class HttpTimeoutOverrideTests(unittest.TestCase):
    def test_no_override_uses_default_behavior(self) -> None:
        self.assertIsNone(_connect_timeout_override("wiki", {"id": "wiki"}))

    def test_explicit_override_is_used(self) -> None:
        self.assertEqual(
            _connect_timeout_override(
                "wiki",
                {"id": "wiki", "connect_timeout_override": 7.5},
            ),
            7.5,
        )

    def test_run_http_uses_default_connect_timeout_when_override_missing(self) -> None:
        response = Mock(status_code=200)
        with patch("app.checks.http_check.requests.get", return_value=response) as mock_get:
            run_http("http://example.local/health", timeout_s=3)

        mock_get.assert_called_once_with("http://example.local/health", timeout=(3, 3))

    def test_run_http_uses_override_connect_timeout(self) -> None:
        response = Mock(status_code=200)
        with patch("app.checks.http_check.requests.get", return_value=response) as mock_get:
            run_http("http://example.local/health", timeout_s=3, connect_timeout_s=9.0)

        mock_get.assert_called_once_with("http://example.local/health", timeout=(9.0, 3))

    def test_runner_applies_ollama_connect_timeout_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "runner-ollama-timeout.sqlite3")
            store = StateStore(db_path=db_path)
            checks = {
                "ollama": {
                    "id": "ollama",
                    "type": "http",
                    "url": "http://192.168.50.201:11434/api/tags",
                    "timeout_s": 3,
                    "down_threshold": 2,
                }
            }
            with patch("app.runner.load_registry", return_value=object()), patch(
                "app.runner.apply_defaults", return_value=checks
            ), patch(
                "app.runner.get_health_summary",
                return_value={"status": "ok", "issues": []},
            ), patch(
                "app.runner.run_http",
                return_value=CheckResult(ok=True, latency_ms=5, status_code=200),
            ) as run_http_mock:
                run_once(store, notifier=None)

        run_http_mock.assert_called_once_with(
            "http://192.168.50.201:11434/api/tags",
            timeout_s=3,
            connect_timeout_s=9.0,
        )


if __name__ == "__main__":
    unittest.main()
