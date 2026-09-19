import unittest

from pydantic import ValidationError

from app.models import FrigateCheck, Registry
from app.registry import apply_defaults


class FrigateRegistryTests(unittest.TestCase):
    def test_frigate_model_defaults_and_registry_normalization(self) -> None:
        registry = Registry.model_validate(
            {
                "checks": [
                    {
                        "id": "frigate",
                        "type": "frigate",
                        "base_url": "http://frigate.local:5000",
                        "required_cameras": ["FrontNorth", "Driveway"],
                        "down_threshold": 2,
                    }
                ]
            }
        )

        self.assertIsInstance(registry.checks[0], FrigateCheck)
        check = apply_defaults(registry)["frigate"]
        self.assertEqual(check["min_recording_storage_mb"], 1_500_000)
        self.assertEqual(check["max_recording_age_s"], 120)
        self.assertEqual(check["startup_grace_s"], 120)
        self.assertEqual(check["down_threshold"], 2)

    def test_required_cameras_must_be_present_and_unique(self) -> None:
        base = {
            "id": "frigate",
            "type": "frigate",
            "base_url": "http://frigate.local:5000",
        }
        for cameras in ([], ["FrontNorth", "FrontNorth"], [""]):
            with self.subTest(cameras=cameras), self.assertRaises(ValidationError):
                FrigateCheck.model_validate({**base, "required_cameras": cameras})

    def test_frigate_threshold_values_are_validated(self) -> None:
        base = {
            "id": "frigate",
            "type": "frigate",
            "base_url": "http://frigate.local:5000",
            "required_cameras": ["FrontNorth"],
        }
        for field, value in (
            ("min_recording_storage_mb", 0),
            ("max_recording_age_s", 0),
            ("startup_grace_s", -1),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                FrigateCheck.model_validate({**base, field: value})


if __name__ == "__main__":
    unittest.main()
