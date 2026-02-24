import tempfile
import unittest
from pathlib import Path

from app.state import StateStore


class DownThresholdStateTests(unittest.TestCase):
    def test_down_threshold_one_transitions_on_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "threshold1.sqlite3"))
            store.ensure_check("svc", "http", down_threshold=1)

            store.update("svc", ok=True, latency_ms=5, status_code=200, down_threshold=1)  # INIT
            event = store.update("svc", ok=False, latency_ms=8, status_code=503, down_threshold=1)

            self.assertIsNotNone(event)
            self.assertEqual(event["event"], "DOWN")
            state = store.check_state("svc")
            self.assertEqual(state["ok"], False)
            self.assertEqual(state["fail_count"], 1)
            self.assertEqual(state["down_threshold"], 1)

    def test_down_threshold_two_requires_second_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "threshold2.sqlite3"))
            store.ensure_check("svc", "http", down_threshold=2)

            store.update("svc", ok=True, latency_ms=5, status_code=200, down_threshold=2)  # INIT

            event1 = store.update("svc", ok=False, latency_ms=8, status_code=503, down_threshold=2)
            self.assertIsNone(event1)
            state1 = store.check_state("svc")
            self.assertEqual(state1["ok"], True)
            self.assertEqual(state1["fail_count"], 1)

            event2 = store.update("svc", ok=False, latency_ms=9, status_code=503, down_threshold=2)
            self.assertIsNotNone(event2)
            self.assertEqual(event2["event"], "DOWN")
            state2 = store.check_state("svc")
            self.assertEqual(state2["ok"], False)
            self.assertEqual(state2["fail_count"], 2)

    def test_recovery_transitions_up_and_resets_fail_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "recover.sqlite3"))
            store.ensure_check("svc", "http", down_threshold=2)

            store.update("svc", ok=True, latency_ms=5, status_code=200, down_threshold=2)  # INIT
            store.update("svc", ok=False, latency_ms=8, status_code=503, down_threshold=2)
            store.update("svc", ok=False, latency_ms=9, status_code=503, down_threshold=2)  # DOWN

            event = store.update("svc", ok=True, latency_ms=4, status_code=200, down_threshold=2)
            self.assertIsNotNone(event)
            self.assertEqual(event["event"], "UP")
            state = store.check_state("svc")
            self.assertEqual(state["ok"], True)
            self.assertEqual(state["fail_count"], 0)

    def test_flap_sequence_with_threshold_two(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(db_path=str(Path(td) / "flap.sqlite3"))
            store.ensure_check("svc", "http", down_threshold=2)

            store.update("svc", ok=True, latency_ms=5, status_code=200, down_threshold=2)  # INIT
            e1 = store.update("svc", ok=False, latency_ms=8, status_code=503, down_threshold=2)
            e2 = store.update("svc", ok=False, latency_ms=9, status_code=503, down_threshold=2)
            e3 = store.update("svc", ok=True, latency_ms=4, status_code=200, down_threshold=2)
            e4 = store.update("svc", ok=False, latency_ms=7, status_code=503, down_threshold=2)
            e5 = store.update("svc", ok=False, latency_ms=9, status_code=503, down_threshold=2)

            self.assertIsNone(e1)
            self.assertEqual(e2["event"], "DOWN")
            self.assertEqual(e3["event"], "UP")
            self.assertIsNone(e4)
            self.assertEqual(e5["event"], "DOWN")


if __name__ == "__main__":
    unittest.main()
