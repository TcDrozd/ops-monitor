import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


class AlertTests(unittest.TestCase):
    def _load_main_module(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["OPSMONITOR_DB_PATH"] = str(Path(td) / "test-alerts.sqlite3")
            mod = importlib.import_module("app.main")
            return importlib.reload(mod)

    def test_alerts_test_success(self) -> None:
        main_mod = self._load_main_module()

        with patch.object(main_mod.settings, "NTFY_URL", "http://ntfy.local"), patch.object(
            main_mod.settings, "NTFY_TOPIC", "ops"
        ), patch.object(main_mod, "load_registry", return_value=object()), patch.object(
            main_mod,
            "apply_defaults",
            return_value={
                "demo": {
                    "id": "demo",
                    "type": "http",
                    "url": "http://example.local/health",
                }
            },
        ), patch.object(main_mod, "NtfyNotifier") as notifier_cls:
            resp = main_mod.alerts_test("demo")

            notifier_cls.assert_called_once()
            notifier_cls.return_value.send_down.assert_called_once()
            self.assertEqual(resp, {"ok": True, "check_id": "demo", "channel": "ntfy"})

    def test_alerts_test_missing_ntfy_config(self) -> None:
        main_mod = self._load_main_module()

        with patch.object(main_mod.settings, "NTFY_URL", None), patch.object(
            main_mod.settings, "NTFY_TOPIC", None
        ):
            with self.assertRaises(HTTPException) as ctx:
                main_mod.alerts_test("demo")

            self.assertEqual(ctx.exception.status_code, 400)

    def test_alerts_test_unknown_check(self) -> None:
        main_mod = self._load_main_module()

        with patch.object(main_mod.settings, "NTFY_URL", "http://ntfy.local"), patch.object(
            main_mod.settings, "NTFY_TOPIC", "ops"
        ), patch.object(main_mod, "load_registry", return_value=object()), patch.object(
            main_mod, "apply_defaults", return_value={}
        ):
            with self.assertRaises(HTTPException) as ctx:
                main_mod.alerts_test("missing")

            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
