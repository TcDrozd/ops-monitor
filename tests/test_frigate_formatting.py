import unittest

from app.formatting import format_transition


class FrigateFormattingTests(unittest.TestCase):
    def test_transition_uses_frigate_base_url(self) -> None:
        title, message = format_transition(
            event={"event": "DOWN", "ts": "2026-09-19T12:00:00Z"},
            check={
                "id": "frigate",
                "type": "frigate",
                "base_url": "http://frigate.local:5000",
            },
            state={"latency_ms": 12, "status_code": 200, "error": "stale"},
        )

        self.assertEqual(title, "[DOWN] frigate")
        self.assertIn("Target: http://frigate.local:5000", message)
        self.assertIn("Error: stale", message)


if __name__ == "__main__":
    unittest.main()
