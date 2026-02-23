from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class NtfyConfig:
    base_url: str
    topic: str
    priority_down: int = 4
    priority_up: int = 2


class NtfyNotifier:
    def __init__(self, cfg: NtfyConfig) -> None:
        self.cfg = cfg

    def _post(
        self, title: str, message: str, priority: int, tags: Optional[str] = None
    ) -> None:
        url = f"{self.cfg.base_url.rstrip('/')}/{self.cfg.topic}"
        headers = {
            "Title": title,
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = tags  # comma-separated emoji or tag words
        # Keep it simple: plain text message body
        requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)

    def send_down(self, title: str, message: str) -> None:
        self._post(
            title, message, priority=self.cfg.priority_down, tags="rotating_light,down"
        )

    def send_up(self, title: str, message: str) -> None:
        self._post(
            title, message, priority=self.cfg.priority_up, tags="white_check_mark,up"
        )
