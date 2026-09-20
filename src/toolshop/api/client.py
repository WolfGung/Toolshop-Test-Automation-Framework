"""Thin HTTP client for the Toolshop API.

Kept deliberately small: it owns the base URL, timeouts and JSON decoding so
tests assert on data, not on transport plumbing.
"""
from __future__ import annotations

from typing import Any

import httpx

from toolshop.config import settings


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        self._client = httpx.Client(
            base_url=base_url or settings.api_base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str, **params: Any) -> httpx.Response:
        return self._client.get(path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        return self._client.post(path, json=payload)
