import unittest
from unittest.mock import Mock, patch

import requests

from app.clients import proxmox_stats


class ProxmoxStatsClientTests(unittest.TestCase):
    def test_get_health_summary_success(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"status": "ok", "issues": []}

        with patch.object(
            proxmox_stats.settings, "PROXMOX_STATS_BASE_URL", "http://proxmox-stats.local"
        ), patch.object(proxmox_stats.settings, "PROXMOX_STATS_TIMEOUT_SECONDS", 2.5), patch(
            "app.clients.proxmox_stats.requests.get", return_value=response
        ) as mock_get:
            payload = proxmox_stats.get_health_summary()

        self.assertEqual(payload, {"status": "ok", "issues": []})
        mock_get.assert_called_once_with(
            "http://proxmox-stats.local/api/health/summary",
            timeout=2.5,
        )

    def test_get_health_summary_timeout_returns_unavailable(self) -> None:
        with patch.object(
            proxmox_stats.settings, "PROXMOX_STATS_BASE_URL", "http://proxmox-stats.local"
        ), patch.object(proxmox_stats.settings, "PROXMOX_STATS_TIMEOUT_SECONDS", 2.5), patch(
            "app.clients.proxmox_stats.requests.get",
            side_effect=requests.Timeout("timed out"),
        ):
            payload = proxmox_stats.get_health_summary()

        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("timed out", payload["error"])

    def test_get_health_summary_non_200_returns_unavailable(self) -> None:
        response = Mock(status_code=503)

        with patch.object(
            proxmox_stats.settings, "PROXMOX_STATS_BASE_URL", "http://proxmox-stats.local"
        ), patch.object(proxmox_stats.settings, "PROXMOX_STATS_TIMEOUT_SECONDS", 2.5), patch(
            "app.clients.proxmox_stats.requests.get", return_value=response
        ):
            payload = proxmox_stats.get_health_summary()

        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("503", payload["error"])

    def test_get_health_summary_invalid_json_returns_unavailable(self) -> None:
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("no json object could be decoded")

        with patch.object(
            proxmox_stats.settings, "PROXMOX_STATS_BASE_URL", "http://proxmox-stats.local"
        ), patch.object(proxmox_stats.settings, "PROXMOX_STATS_TIMEOUT_SECONDS", 2.5), patch(
            "app.clients.proxmox_stats.requests.get", return_value=response
        ):
            payload = proxmox_stats.get_health_summary()

        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("invalid JSON", payload["error"])


if __name__ == "__main__":
    unittest.main()
