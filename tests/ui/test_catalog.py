"""Catalog browsing: grid, sorting, product detail."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page

from toolshop.ui.pages.home_page import HomePage
from toolshop.ui.pages.product_page import ProductPage

pytestmark = [pytest.mark.ui, allure.feature("Catalog")]


@pytest.mark.smoke
@allure.title("The landing page renders a full page of products")
def test_catalog_renders(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()

    assert home.product_cards.count() == 9, "the first page should hold nine products"
    assert all(name for name in home.product_names), "a product card has no name"
    assert all(price > 0 for price in home.product_prices), "a product is priced at zero"


@allure.title("Sorting by price low to high orders the grid ascending")
def test_sort_price_ascending(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()

    home.sort_by("Price (Low - High)")

    prices = home.product_prices
    assert prices == sorted(prices), f"not ascending: {prices}"


@allure.title("Sorting by name Z to A reverses the alphabetical order")
def test_sort_name_descending(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()

    home.sort_by("Name (Z - A)")

    names = [n.lower() for n in home.product_names]
    assert names == sorted(names, reverse=True), f"not reversed: {names}"


@pytest.mark.smoke
@allure.title("A product card opens a detail page with matching name and price")
def test_open_product_detail(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()

    expected_name = home.product_names[0]
    expected_price = home.product_prices[0]

    home.open_product(0)

    detail = ProductPage(page)
    detail.wait_for_loaded()
    assert detail.name == expected_name
    assert detail.unit_price == expected_price
