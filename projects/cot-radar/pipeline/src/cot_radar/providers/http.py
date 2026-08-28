from __future__ import annotations

from typing import Any, Protocol

import httpx


class HttpLike(Protocol):
    def get_json(self, url: str, params: dict[str, str | int]) -> Any: ...

    def get_text(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> str: ...


class HttpClient:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {"User-Agent": "macro-radar/0.1 research@users.noreply.github.com"}

    def get_json(self, url: str, params: dict[str, str | int]) -> Any:
        response = httpx.get(
            url,
            params=params,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()

    def get_text(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> str:
        response = httpx.get(
            url,
            params=params,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
