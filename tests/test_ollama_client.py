import unittest
from unittest.mock import Mock, patch

from app.api_schemas import REPORT_JSON_SCHEMA
from app.clients.ollama_client import generate_json_report
from app.reporting import build_report_prompt


class OllamaClientTests(unittest.TestCase):
    def test_generate_json_report_sends_schema_format(self) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"response": "{\"headline\":\"x\"}"}

        with patch("app.clients.ollama_client.requests.post", return_value=response) as mock_post:
            generate_json_report(
                "prompt text",
                base_url="http://ollama.local:11434",
                model="llama3.1:8b",
                timeout_s=30,
            )

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["format"], REPORT_JSON_SCHEMA)

    def test_report_prompt_mentions_schema(self) -> None:
        prompt = build_report_prompt(facts={"foo": "bar"})
        self.assertIn("schema", prompt.lower())


if __name__ == "__main__":
    unittest.main()
