"""Brands and categories."""
from __future__ import annotations

import allure
import pytest

from toolshop.api.products import CatalogApi

pytestmark = [pytest.mark.api, allure.feature("Catalog API")]


@pytest.mark.smoke
@allure.title("Brands are returned with a unique slug each")
def test_brands(catalog_api: CatalogApi) -> None:
    response = catalog_api.brands()

    assert response.status_code == 200
    brands = response.json()
    assert brands, "no brands returned"

    slugs = [b["slug"] for b in brands]
    assert len(slugs) == len(set(slugs)), "duplicate brand slugs"
    for brand in brands:
        assert brand["name"].strip(), f"brand {brand['id']} has an empty name"


@allure.title("Categories expose a parent-child hierarchy")
def test_categories_hierarchy(catalog_api: CatalogApi) -> None:
    response = catalog_api.categories()

    assert response.status_code == 200
    categories = response.json()
    by_id = {c["id"]: c for c in categories}

    roots = [c for c in categories if c["parent_id"] is None]
    children = [c for c in categories if c["parent_id"] is not None]

    assert roots, "no top-level categories"
    assert children, "no sub-categories"
    for child in children:
        assert child["parent_id"] in by_id, (
            f"{child['name']} points at a parent that is not in the response"
        )
