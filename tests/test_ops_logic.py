import unittest

from app.ops_logic import compute_overall_status, summarize_checks


class OpsLogicTests(unittest.TestCase):
    def test_compute_overall_status_rules(self) -> None:
        cases = [
            (True, False, "ok", "crit"),
            (False, True, "ok", "warn"),
            (False, False, "warn", "warn"),
            (False, False, "ok", "ok"),
            (False, False, "crit", "ok"),
        ]

        for core_down, non_core_down, proxmox_status, expected in cases:
            with self.subTest(
                core_down=core_down,
                non_core_down=non_core_down,
                proxmox_status=proxmox_status,
            ):
                self.assertEqual(
                    compute_overall_status(core_down, non_core_down, proxmox_status),
                    expected,
                )

    def test_summarize_checks(self) -> None:
        checks = {
            "core-api": {"ok": False},
            "edge-cache": {"ok": False},
            "ntfy": {"ok": True},
            "new-service": {"ok": None},
        }

        up, down, down_list, core_down, non_core_down = summarize_checks(
            check_results=checks,
            core_check_ids={"core-api"},
        )

        self.assertEqual(up, 1)
        self.assertEqual(down, 2)
        self.assertEqual(down_list, ["core-api", "edge-cache"])
        self.assertTrue(core_down)
        self.assertTrue(non_core_down)


if __name__ == "__main__":
    unittest.main()
