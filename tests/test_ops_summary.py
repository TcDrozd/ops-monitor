import importlib
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


class OpsSummaryEndpointTests(unittest.TestCase):
    def _load_main_module(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["OPSMONITOR_DB_PATH"] = str(Path(td) / "test-ops-summary.sqlite3")
            mod = importlib.import_module("app.main")
            mod = importlib.reload(mod)
            mod.store = mod.StateStore(db_path=None)
            return mod

    def test_ops_summary_with_cached_proxmox_payload(self) -> None:
        main_mod = self._load_main_module()

        main_mod.store.ensure_check("core-api", "http")
        main_mod.store.ensure_check("wiki", "http")
        main_mod.store.update("core-api", ok=True, latency_ms=10, status_code=200)
        main_mod.store.update("wiki", ok=False, latency_ms=10, status_code=503, error="down")
        main_mod.store.update_proxmox_stats(
            {
                "status": "warn",
                "issues": [{"kind": "ct_disk_high", "vmid": 111, "usage_percent": 91.6}],
            },
            fetch_ts=datetime(2026, 2, 23, 14, 11, 45, tzinfo=timezone.utc),
        )

        with patch.object(main_mod.settings, "OPS_CORE_CHECK_IDS", ("core-api",)):
            payload = main_mod.ops_summary()

        self.assertEqual(payload["overall"], "warn")
        self.assertEqual(payload["services"]["up"], 1)
        self.assertEqual(payload["services"]["down"], 1)
        self.assertEqual(payload["services"]["down_list"], ["wiki"])
        self.assertEqual(payload["proxmox"]["status"], "warn")
        self.assertEqual(len(payload["proxmox"]["issues"]), 1)
        self.assertTrue(payload["recent_events"])

    def test_ops_summary_with_proxmox_unavailable_and_no_payload(self) -> None:
        main_mod = self._load_main_module()

        main_mod.store.ensure_check("svc", "http")
        main_mod.store.update("svc", ok=True, latency_ms=3, status_code=200)
        main_mod.store.update_proxmox_stats(
            {"status": "unavailable", "error": "connection refused"},
            fetch_ts=datetime(2026, 2, 23, 14, 11, 45, tzinfo=timezone.utc),
        )

        payload = main_mod.ops_summary()

        self.assertEqual(payload["proxmox"]["status"], "unknown")
        self.assertEqual(payload["proxmox"]["last_error"], "connection refused")
        self.assertEqual(payload["docker"]["status"], "unknown")

    def test_ops_summary_does_not_make_network_calls(self) -> None:
        main_mod = self._load_main_module()

        with patch(
            "app.clients.proxmox_stats.requests.get",
            side_effect=AssertionError("network call should not happen"),
        ):
            main_mod.ops_summary()


if __name__ == "__main__":
    unittest.main()
