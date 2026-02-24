import unittest

from app.models import Defaults, HttpCheck, Registry
from app.registry import apply_defaults


class RegistryDownThresholdTests(unittest.TestCase):
    def test_apply_defaults_sets_down_threshold_default(self) -> None:
        reg = Registry(
            defaults=Defaults(),
            checks=[HttpCheck(id="svc", type="http", url="http://example.com")],
        )

        checks = apply_defaults(reg)
        self.assertEqual(checks["svc"]["down_threshold"], 1)

    def test_apply_defaults_preserves_explicit_down_threshold(self) -> None:
        reg = Registry(
            defaults=Defaults(),
            checks=[
                HttpCheck(
                    id="svc",
                    type="http",
                    url="http://example.com",
                    down_threshold=3,
                )
            ],
        )

        checks = apply_defaults(reg)
        self.assertEqual(checks["svc"]["down_threshold"], 3)


if __name__ == "__main__":
    unittest.main()
