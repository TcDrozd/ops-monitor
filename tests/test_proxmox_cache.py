from datetime import datetime, timezone
import unittest

from app.state import ProxmoxStatsCache, apply_proxmox_fetch_result


class ProxmoxCacheLogicTests(unittest.TestCase):
    def test_success_updates_payload_and_clears_error(self) -> None:
        prev = ProxmoxStatsCache(
            last_payload={"status": "warn"},
            last_fetch_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_error="timeout",
        )
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)

        next_state = apply_proxmox_fetch_result(
            current=prev,
            fetch_result={"status": "ok", "issues": []},
            fetch_ts=now,
        )

        self.assertEqual(next_state.last_payload, {"status": "ok", "issues": []})
        self.assertEqual(next_state.last_fetch_ts, now)
        self.assertIsNone(next_state.last_error)

    def test_failure_keeps_previous_payload_and_sets_error(self) -> None:
        prev = ProxmoxStatsCache(
            last_payload={"status": "ok", "issues": []},
            last_fetch_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_error=None,
        )
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)

        next_state = apply_proxmox_fetch_result(
            current=prev,
            fetch_result={"status": "unavailable", "error": "connection refused"},
            fetch_ts=now,
        )

        self.assertEqual(next_state.last_payload, {"status": "ok", "issues": []})
        self.assertEqual(next_state.last_fetch_ts, now)
        self.assertEqual(next_state.last_error, "connection refused")

    def test_timestamp_updates_on_each_poll_attempt(self) -> None:
        prev = ProxmoxStatsCache(
            last_payload=None,
            last_fetch_ts=None,
            last_error=None,
        )
        first = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
        second = datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc)

        state_one = apply_proxmox_fetch_result(
            current=prev,
            fetch_result={"status": "unavailable", "error": "timeout"},
            fetch_ts=first,
        )
        state_two = apply_proxmox_fetch_result(
            current=state_one,
            fetch_result={"status": "unavailable", "error": "timeout"},
            fetch_ts=second,
        )

        self.assertEqual(state_one.last_fetch_ts, first)
        self.assertEqual(state_two.last_fetch_ts, second)


if __name__ == "__main__":
    unittest.main()
