import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class OpsHealthEndpointTests(unittest.TestCase):
    def _load_main_module(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["OPSMONITOR_DB_PATH"] = str(Path(td) / "test-ops-health.sqlite3")
            mod = importlib.import_module("app.main")
            mod = importlib.reload(mod)
            mod.store = mod.StateStore(db_path=None)
            return mod

    def test_ops_health_never_fetched(self) -> None:
        main_mod = self._load_main_module()

        payload = main_mod.ops_health()

        self.assertEqual(payload["dependencies"]["proxmox_stats"]["status"], "unknown")
        self.assertEqual(payload["dependencies"]["proxmox_stats"]["note"], "proxmox-stats not polled yet")

    def test_ops_health_recently_successful(self) -> None:
        main_mod = self._load_main_module()
        main_mod.store.update_proxmox_stats(
            {"status": "ok", "issues": []},
            fetch_ts=datetime.now(timezone.utc) - timedelta(seconds=10),
        )

        payload = main_mod.ops_health()

        self.assertEqual(payload["dependencies"]["proxmox_stats"]["status"], "ok")
        self.assertIsNone(payload["dependencies"]["proxmox_stats"]["last_error"])

    def test_ops_health_recently_failed(self) -> None:
        main_mod = self._load_main_module()
        main_mod.store.update_proxmox_stats(
            {"status": "unavailable", "error": "timeout"},
            fetch_ts=datetime.now(timezone.utc) - timedelta(seconds=10),
        )

        payload = main_mod.ops_health()

        self.assertEqual(payload["dependencies"]["proxmox_stats"]["status"], "unavailable")
        self.assertEqual(payload["dependencies"]["proxmox_stats"]["last_error"], "timeout")

    def test_ops_health_stale_data(self) -> None:
        main_mod = self._load_main_module()
        main_mod.store.update_proxmox_stats(
            {"status": "ok", "issues": []},
            fetch_ts=datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        payload = main_mod.ops_health()

        self.assertEqual(payload["dependencies"]["proxmox_stats"]["status"], "unknown")
        self.assertEqual(payload["dependencies"]["proxmox_stats"]["note"], "stale proxmox-stats poll data")


if __name__ == "__main__":
    unittest.main()
