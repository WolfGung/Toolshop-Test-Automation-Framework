"""Search endpoint."""
from __future__ import annotations

import allure
import pytest

from toolshop.api.products import ProductsApi, page_items

pytestmark = [pytest.mark.api, allure.feature("Search API")]


@pytest.mark.smoke
@allure.title("Search returns products matching the query")
def test_search_returns_matches(products_api: ProductsApi) -> None:
    response = products_api.search("pliers")

    assert response.status_code == 200
    products = page_items(response.json())
    assert products, "search for a known product returned nothing"

    for product in products:
        haystack = f"{product['name']} {product['description']}".lower()
        assert "plier" in haystack, f"unrelated result: {product['name']}"


@pytest.mark.negative
@allure.title("A query with no matches returns an empty result, not an error")
def test_search_without_matches(products_api: ProductsApi) -> None:
    response = products_api.search("zzzzz-no-such-product-zzzzz")

    assert response.status_code == 200
    assert page_items(response.json()) == []


@pytest.mark.negative
@allure.title("Search input is not reflected back as executable markup")
def test_search_does_not_reflect_markup(products_api: ProductsApi) -> None:
    payload = "<script>alert(1)</script>"

    response = products_api.search(payload)

    assert response.status_code in (200, 422)
    assert "<script>" not in response.text
