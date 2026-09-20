"""Product catalog endpoints."""
from __future__ import annotations

import allure
import pytest

from toolshop.api.products import ProductsApi, page_items

pytestmark = [pytest.mark.api, allure.feature("Catalog API")]

REQUIRED_FIELDS = {"id", "name", "description", "price", "category", "brand"}


@pytest.mark.smoke
@allure.title("GET /products returns a populated first page")
def test_products_first_page(products_api: ProductsApi) -> None:
    response = products_api.list()

    assert response.status_code == 200
    body = response.json()
    assert body["current_page"] == 1
    assert body["total"] > 0
    assert len(page_items(body)) == body["per_page"]


@allure.title("Every product carries the fields the storefront renders")
def test_product_schema(products_api: ProductsApi) -> None:
    products = page_items(products_api.list().json())

    for product in products:
        missing = REQUIRED_FIELDS - product.keys()
        assert not missing, f"{product.get('name')} is missing {sorted(missing)}"
        assert isinstance(product["price"], (int, float))
        assert product["price"] > 0, f"{product['name']} is priced at {product['price']}"


@allure.title("Pagination returns distinct pages")
def test_pagination_pages_do_not_overlap(products_api: ProductsApi) -> None:
    first = page_items(products_api.list(page=1).json())
    second = page_items(products_api.list(page=2).json())

    first_ids = {p["id"] for p in first}
    second_ids = {p["id"] for p in second}

    assert first_ids, "page 1 is empty"
    assert second_ids, "page 2 is empty"
    assert not first_ids & second_ids, "the same product appears on both pages"


@allure.title("A single product can be fetched by the id from the listing")
def test_fetch_product_by_id(products_api: ProductsApi) -> None:
    listed = page_items(products_api.list().json())[0]

    response = products_api.by_id(listed["id"])

    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == listed["id"]
    assert fetched["name"] == listed["name"]
    assert fetched["price"] == listed["price"]


@pytest.mark.negative
@allure.title("An unknown product id is rejected, not answered with a body")
def test_unknown_product_id(products_api: ProductsApi) -> None:
    response = products_api.by_id("this-id-does-not-exist")

    assert response.status_code in (404, 422), (
        f"expected a client error, got {response.status_code}"
    )


@pytest.mark.boundary
@allure.title("A price filter returns only products inside the range")
def test_price_filter_respects_bounds(products_api: ProductsApi) -> None:
    low, high = 1, 10

    products = page_items(products_api.between_price(low, high).json())

    assert products, "no products found in the requested price range"
    outside = [p for p in products if not low <= p["price"] <= high]
    assert not outside, f"outside {low}-{high}: {[(p['name'], p['price']) for p in outside]}"
