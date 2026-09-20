"""Resource-level helpers over the raw client."""
from __future__ import annotations

from typing import Any

import httpx

from toolshop.api.client import ApiClient


class ProductsApi:
    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def list(self, page: int | None = None) -> httpx.Response:
        return self._client.get("/products", page=page)

    def by_id(self, product_id: str) -> httpx.Response:
        return self._client.get(f"/products/{product_id}")

    def search(self, query: str) -> httpx.Response:
        return self._client.get("/products/search", q=query)

    def between_price(self, low: float, high: float) -> httpx.Response:
        return self._client.get("/products", between=f"price,{low},{high}")


class CatalogApi:
    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def brands(self) -> httpx.Response:
        return self._client.get("/brands")

    def categories(self) -> httpx.Response:
        return self._client.get("/categories")


def page_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Paginated endpoints wrap results in `data`; unwrap them in one place."""
    return payload["data"]
