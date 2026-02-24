import unittest

from app.api_schemas import REPORT_JSON_SCHEMA


class ReportSchemaTests(unittest.TestCase):
    def test_report_json_schema_contains_expected_properties(self) -> None:
        self.assertIsInstance(REPORT_JSON_SCHEMA, dict)
        self.assertTrue(REPORT_JSON_SCHEMA)
        properties = REPORT_JSON_SCHEMA.get("properties")
        self.assertIsInstance(properties, dict)
        self.assertIn("headline", properties)
        self.assertIn("recommendations", properties)


if __name__ == "__main__":
    unittest.main()
