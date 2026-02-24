from __future__ import annotations

from typing import Any

import requests

from app.api_schemas import REPORT_JSON_SCHEMA


class OllamaClientError(RuntimeError):
    pass


def generate_json_report(
    prompt: str,
    *,
    base_url: str,
    model: str,
    timeout_s: int,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/generate"
    options: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": REPORT_JSON_SCHEMA,
                "options": options,
            },
            timeout=timeout_s,
        )
    except requests.Timeout as exc:
        raise OllamaClientError(f"Ollama API timed out after {timeout_s}s") from exc
    except requests.ConnectionError as exc:
        raise OllamaClientError(
            f"Ollama API connection error: {exc.__class__.__name__}: {exc}"
        ) from exc
    except requests.RequestException as exc:
        raise OllamaClientError(
            f"Failed to reach Ollama API: {exc.__class__.__name__}: {exc}"
        ) from exc

    if resp.status_code >= 400:
        snippet = resp.text[:240].replace("\n", "\\n")
        raise OllamaClientError(
            f"Ollama API returned HTTP {resp.status_code}: {snippet}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        snippet = resp.text[:240].replace("\n", "\\n")
        raise OllamaClientError(
            f"Ollama API returned invalid JSON envelope: {snippet}"
        ) from exc

    if not isinstance(payload, dict):
        raise OllamaClientError("Ollama API returned an unexpected payload")
    return payload
