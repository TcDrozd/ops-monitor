import unittest
import importlib
import os
import tempfile
from pathlib import Path



class OpenAPITests(unittest.TestCase):
    def test_openapi_schema_generation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            os.environ["OPSMONITOR_DB_PATH"] = str(Path(td) / "test-openapi.sqlite3")
            main_mod = importlib.import_module("app.main")
            app = main_mod.app

        schema = app.openapi()

        self.assertIsInstance(schema, dict)
        self.assertIn("openapi", schema)
        self.assertIn("paths", schema)

        paths = schema["paths"]
        self.assertIn("/api/status/checks", paths)
        self.assertIn("/api/status/summary", paths)
        self.assertIn("/api/status/events", paths)
        self.assertIn("/api/ops/summary", paths)
        self.assertIn("/api/ops/health", paths)
        self.assertIn("/api/reports/generate", paths)
        self.assertIn("/api/registry", paths)
        self.assertIn("/api/alerts/test", paths)


if __name__ == "__main__":
    unittest.main()
