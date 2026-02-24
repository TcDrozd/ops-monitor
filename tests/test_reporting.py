import json
import unittest

from app.api_schemas import ReportData
from app.reporting import (
    normalize_report_obj,
    parse_report_data,
    render_report_markdown,
    sanity_check_report_dict,
    validate_report_data,
)


class ReportingHelpersTests(unittest.TestCase):
    def test_parse_report_data_valid_json_passes(self) -> None:
        raw = json.dumps(
            {
                "headline": "Overall warn",
                "notable_events": [
                    {
                        "time": "2026-02-23T22:37:21Z",
                        "summary": "open-webui flapped",
                        "severity": "warn",
                    }
                ],
                "current_issues": [{"summary": "disk high", "suggestion": "clean logs"}],
                "recommendations": ["Investigate service"],
            }
        )
        payload = parse_report_data(raw)
        self.assertEqual(payload.headline, "Overall warn")
        self.assertEqual(payload.notable_events[0].severity, "warn")

    def test_parse_report_data_invalid_json_fails(self) -> None:
        with self.assertRaises(ValueError):
            parse_report_data("not json")

    def test_parse_report_data_normalizes_bad_severity(self) -> None:
        raw = json.dumps(
            {
                "headline": "x",
                "notable_events": [{"time": None, "summary": "a", "severity": "critical"}],
                "current_issues": [],
                "recommendations": [],
            }
        )
        payload = parse_report_data(raw)
        self.assertEqual(payload.notable_events[0].severity, "crit")

    def test_normalize_report_obj_aliases_and_shapes(self) -> None:
        raw = {
            "title": "Health Checks",
            "events": ["A happened"],
            "issues": ["Disk high"],
            "recs": [{"text": "Do X"}],
            "extra": "ignored",
        }
        normalized = normalize_report_obj(raw)
        self.assertEqual(
            set(normalized.keys()),
            {"headline", "notable_events", "current_issues", "recommendations"},
        )
        self.assertEqual(normalized["headline"], "Health Checks")
        self.assertEqual(normalized["notable_events"][0]["summary"], "A happened")
        self.assertEqual(normalized["current_issues"][0]["summary"], "Disk high")
        self.assertEqual(normalized["recommendations"], ["Do X"])

    def test_parse_report_data_handles_double_stringified_json(self) -> None:
        raw = json.dumps(
            json.dumps(
                {
                    "headline": "Health Checks",
                    "notable_events": [],
                    "current_issues": [],
                    "recommendations": [],
                }
            )
        )
        payload = parse_report_data(raw)
        self.assertEqual(payload.headline, "Health Checks")

    def test_sanity_truncates_lists(self) -> None:
        payload = {
            "headline": "Ops Report",
            "notable_events": [{"summary": "x", "severity": "warn"} for _ in range(50)],
            "current_issues": [{"summary": "y", "suggestion": ""} for _ in range(50)],
            "recommendations": [f"r{i}" for i in range(50)],
        }
        sane = sanity_check_report_dict(payload)
        self.assertEqual(len(sane["notable_events"]), 20)
        self.assertEqual(len(sane["current_issues"]), 20)
        self.assertEqual(len(sane["recommendations"]), 20)

    def test_sanity_rejects_overlong_headline(self) -> None:
        payload = {
            "headline": "x" * 201,
            "notable_events": [],
            "current_issues": [],
            "recommendations": [],
        }
        with self.assertRaises(ValueError):
            sanity_check_report_dict(payload)

    def test_validity_gate_accepts_valid_report(self) -> None:
        report = ReportData.model_validate(
            {
                "headline": "Overall warn",
                "notable_events": [],
                "current_issues": [],
                "recommendations": ["Investigate service"],
            }
        )
        valid, reason = validate_report_data(report)
        self.assertTrue(valid)
        self.assertIsNone(reason)

    def test_validity_gate_rejects_empty_headline(self) -> None:
        report = ReportData.model_validate(
            {
                "headline": "   ",
                "notable_events": [],
                "current_issues": [],
                "recommendations": ["Investigate service"],
            }
        )
        valid, reason = validate_report_data(report)
        self.assertFalse(valid)
        self.assertIn("headline", reason or "")

    def test_validity_gate_rejects_empty_content(self) -> None:
        report = ReportData.model_validate(
            {
                "headline": "Overall ok",
                "notable_events": [],
                "current_issues": [],
                "recommendations": [],
            }
        )
        valid, reason = validate_report_data(report)
        self.assertFalse(valid)
        self.assertIn("missing actionable content", reason or "")

    def test_render_report_markdown_stable_output(self) -> None:
        report_data = ReportData.model_validate(
            {
                "headline": "Overall warn: 1 service down",
                "notable_events": [
                    {
                        "time": "2026-02-23T22:37:21Z",
                        "summary": "open-webui flapped twice",
                        "severity": "warn",
                    }
                ],
                "current_issues": [
                    {
                        "summary": "dashboards CT disk at 91.69%",
                        "suggestion": "Expand CT disk or clean logs",
                    }
                ],
                "recommendations": [
                    "Investigate why ollama-lab port 11435 is refusing connections"
                ],
            }
        )
        markdown = render_report_markdown(
            report_data=report_data,
            generated_at="2026-02-24T00:56:40Z",
            range_minutes=1440,
            status_summary={"total": 3, "up": 2, "down": 1, "unknown": 0, "down_checks": [{"id": "wiki"}]},
            sources_info={
                "ops_summary_included": True,
                "status_summary_included": True,
                "events_limit": 200,
                "proxmox_included": True,
            },
        )
        expected = (
            "# Ops Report (2026-02-24T00:56:40Z)\n\n"
            "**Overall:** Overall warn: 1 service down\n\n"
            "## Current status\n"
            "- Window: last 1440 minutes\n"
            "- Checks: total=3, up=2, down=1, unknown=0\n"
            "- Down checks: wiki\n\n"
            "## Notable events\n"
            "- [warn] 2026-02-23T22:37:21Z - open-webui flapped twice\n\n"
            "## Current issues\n"
            "- dashboards CT disk at 91.69% (suggestion: Expand CT disk or clean logs)\n\n"
            "## Recommendations\n"
            "1. Investigate why ollama-lab port 11435 is refusing connections\n\n"
            "## Sources\n"
            "- ops_summary: yes\n"
            "- status_summary: yes\n"
            "- events_limit: 200\n"
            "- proxmox: yes"
        )
        self.assertEqual(markdown, expected)


if __name__ == "__main__":
    unittest.main()
