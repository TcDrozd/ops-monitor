import importlib
import json
import os
import tempfile
import unittest
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.api_schemas import ReportGenerateRequest
from app.clients.ollama_client import OllamaClientError
from app.state import ProxmoxStatsCache


class ReportsGenerateEndpointTests(unittest.TestCase):
    def _load_main_module(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["OPSMONITOR_DB_PATH"] = str(Path(td) / "test-reports.sqlite3")
            mod = importlib.import_module("app.main")
            mod = importlib.reload(mod)
            mod.store = mod.StateStore(db_path=None)
            return mod

    def _asgi_post_json(self, app, path: str, payload: dict) -> tuple[int, bytes]:
        body = json.dumps(payload).encode("utf-8")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        sent_messages: list[dict] = []
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent_messages.append(message)

        asyncio.run(app(scope, receive, send))
        status = 500
        response_body = b""
        for message in sent_messages:
            if message["type"] == "http.response.start":
                status = message["status"]
            if message["type"] == "http.response.body":
                response_body += message.get("body", b"")
        return status, response_body

    def test_route_returns_200_with_stubbed_ollama_response(self) -> None:
        main_mod = self._load_main_module()
        main_mod.store.ensure_check("api", "http")
        main_mod.store.update("api", ok=True, latency_ms=7, status_code=200)
        main_mod.store.update_proxmox_stats(
            {"status": "ok", "issues": []},
            fetch_ts=datetime(2026, 2, 24, 0, 56, 40, tzinfo=timezone.utc),
        )

        with patch.object(
            main_mod,
            "generate_json_report",
            return_value={
                "response": json.dumps(
                    {
                        "headline": "Overall ok",
                        "notable_events": [],
                        "current_issues": [],
                        "recommendations": ["Investigate service"],
                    }
                )
            },
        ):
            status_code, body = self._asgi_post_json(
                main_mod.app, "/api/reports/generate", {"range_minutes": 1440}
            )

        self.assertEqual(status_code, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertIn("markdown", payload)
        self.assertIn("report_json", payload)
        self.assertEqual(payload["sources"]["events_limit"], 200)
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["parse_error"])

    def test_invalid_model_output_returns_ok_with_parse_error(self) -> None:
        main_mod = self._load_main_module()
        with patch.object(
            main_mod, "generate_json_report", return_value={"response": "not valid json"}
        ), self.assertLogs("app.main", level="ERROR") as logs:
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.parse_error)
        self.assertIsNotNone(response.report_json)
        self.assertIn("Failed to parse report JSON output", "\n".join(logs.output))

    def test_facts_gathering_calls_internal_accessors(self) -> None:
        main_mod = self._load_main_module()
        proxmox_cache = ProxmoxStatsCache(
            last_payload={"status": "warn", "issues": []},
            last_fetch_ts=datetime(2026, 2, 24, 0, 56, 40, tzinfo=timezone.utc),
            last_error=None,
        )
        with patch.object(main_mod, "ops_summary", return_value={"overall": "warn"}) as ops_mock, patch.object(
            main_mod,
            "status_summary",
            return_value={"total": 2, "up": 1, "down": 1, "unknown": 0, "down_checks": []},
        ) as status_mock, patch.object(
            main_mod, "status_events", return_value=[]
        ) as events_mock, patch.object(
            main_mod.store, "proxmox_stats_snapshot", return_value=proxmox_cache
        ) as proxmox_mock, patch.object(
            main_mod,
            "generate_json_report",
            return_value={
                "response": json.dumps(
                    {
                        "headline": "Overall warn",
                        "notable_events": [],
                        "current_issues": [],
                        "recommendations": ["Investigate service"],
                    }
                )
            },
        ):
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=60))

        self.assertEqual(response.range.range_minutes, 60)
        ops_mock.assert_called_once_with()
        status_mock.assert_called_once_with()
        events_mock.assert_called_once_with(limit=200)
        proxmox_mock.assert_called_once_with()

    def test_repair_pass_populates_report_json(self) -> None:
        main_mod = self._load_main_module()
        with patch.object(
            main_mod,
            "generate_json_report",
            side_effect=[
                {"response": "not valid json"},
                {
                    "response": json.dumps(
                        {
                            "headline": "Overall ok",
                            "notable_events": [],
                            "current_issues": [],
                            "recommendations": ["Investigate service"],
                        }
                    )
                },
            ],
        ):
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertIsNotNone(response.markdown)
        self.assertIsNotNone(response.parse_error)

    def test_stringified_json_drift_does_not_trigger_convert_pass(self) -> None:
        main_mod = self._load_main_module()
        drift = json.dumps(
            {
                "title": "Health Checks",
                "events": ["A happened"],
                "issues": ["Disk high"],
                "recs": [{"text": "Do X"}],
            }
        )
        with patch.object(
            main_mod,
            "generate_json_report",
            return_value={"response": drift},
        ) as gen_mock:
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertEqual(response.report_json.headline, "Health Checks")
        self.assertEqual(response.report_json.notable_events[0].summary, "A happened")
        self.assertEqual(response.report_json.current_issues[0].summary, "Disk high")
        self.assertEqual(response.report_json.recommendations, ["Do X"])
        self.assertIsNone(response.parse_error)
        self.assertEqual(gen_mock.call_count, 1)

    def test_overlong_headline_triggers_convert_pass(self) -> None:
        main_mod = self._load_main_module()
        first = {
            "response": json.dumps(
                {
                    "headline": "x" * 300,
                    "notable_events": [],
                    "current_issues": [],
                    "recommendations": [],
                }
            )
        }
        second = {
            "response": json.dumps(
                {
                            "headline": "Health Checks",
                            "notable_events": [],
                            "current_issues": [],
                            "recommendations": ["Investigate service"],
                        }
                    )
                }
        with patch.object(main_mod, "generate_json_report", side_effect=[first, second]) as gen_mock:
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertEqual(response.report_json.headline, "Health Checks")
        self.assertIsNotNone(response.parse_error)
        self.assertIn("repaired via second pass", response.parse_error)
        self.assertEqual(gen_mock.call_count, 2)

    def test_repair_path_called_once_then_falls_back(self) -> None:
        main_mod = self._load_main_module()
        invalid = {
            "response": json.dumps(
                {
                    "headline": "Overall ok",
                    "notable_events": [],
                    "current_issues": [],
                    "recommendations": [],
                }
            )
        }
        with patch.object(main_mod, "generate_json_report", side_effect=[invalid, invalid]) as gen_mock:
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertIsNotNone(response.parse_error)
        self.assertEqual(gen_mock.call_count, 2)
        self.assertEqual(response.report_json.current_issues[0].summary, "LLM report generation failed")

    def test_first_pass_ollama_error_returns_best_effort_report(self) -> None:
        main_mod = self._load_main_module()
        with patch.object(
            main_mod,
            "generate_json_report",
            side_effect=OllamaClientError("timed out waiting for model"),
        ):
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertIsNotNone(response.markdown)
        self.assertIsNotNone(response.parse_error)
        self.assertIn("model call failed", response.parse_error)

    def test_first_pass_error_retries_with_longer_timeout(self) -> None:
        main_mod = self._load_main_module()
        with patch.object(
            main_mod,
            "generate_json_report",
            side_effect=[
                OllamaClientError("Ollama API timed out after 30s"),
                {
                    "response": json.dumps(
                        {
                            "headline": "Overall ok",
                            "notable_events": [],
                            "current_issues": [],
                            "recommendations": ["Investigate service"],
                        }
                    )
                },
            ],
        ) as gen_mock:
            response = main_mod.reports_generate(ReportGenerateRequest(range_minutes=1440))

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.report_json)
        self.assertIsNone(response.parse_error)
        self.assertEqual(gen_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
