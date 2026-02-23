import tempfile
import unittest
from pathlib import Path

from app.state import StateStore


class StateStorePersistenceTests(unittest.TestCase):
    def test_state_and_events_restore_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "ops-monitor.sqlite3")

            store1 = StateStore(db_path=db_path, max_events=500)
            store1.ensure_check("http-google", "http")
            store1.update("http-google", ok=False, latency_ms=12, status_code=503, error="boom")
            store1.update("http-google", ok=True, latency_ms=10, status_code=200, error=None)

            store2 = StateStore(db_path=db_path, max_events=500)
            snap = store2.snapshot()

            self.assertIn("http-google", snap)
            self.assertEqual(snap["http-google"]["ok"], True)
            self.assertEqual(snap["http-google"]["status_code"], 200)

            events = store2.events(limit=10)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "UP")
            self.assertEqual(events[1]["event"], "INIT")

    def test_events_bounded_and_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "ops-monitor.sqlite3")

            store1 = StateStore(db_path=db_path, max_events=3)
            store1.ensure_check("tcp-db", "tcp")
            store1.update("tcp-db", ok=False, latency_ms=1, error="x")  # INIT
            store1.update("tcp-db", ok=True, latency_ms=1, error=None)  # UP
            store1.update("tcp-db", ok=False, latency_ms=1, error="y")  # DOWN
            store1.update("tcp-db", ok=True, latency_ms=1, error=None)  # UP

            store2 = StateStore(db_path=db_path, max_events=3)
            events = store2.events(limit=10)

            self.assertEqual(len(events), 3)
            self.assertEqual([e["event"] for e in events], ["UP", "DOWN", "UP"])


if __name__ == "__main__":
    unittest.main()
