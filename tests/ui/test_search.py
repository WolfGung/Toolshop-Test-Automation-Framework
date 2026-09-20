"""Storefront search."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from toolshop.ui.pages.home_page import HomePage

pytestmark = [pytest.mark.ui, allure.feature("Search")]


@pytest.mark.smoke
@allure.title("Searching a known term narrows the grid to matching products")
def test_search_narrows_results(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()
    before = home.product_cards.count()

    home.search("pliers")

    names = home.product_names
    assert names, "search returned no products"
    assert home.product_cards.count() <= before
    assert all("plier" in name.lower() for name in names), names
    expect(home.result_count).to_contain_text(f"{len(names)} products found")


@pytest.mark.negative
@allure.title("A search with no matches shows an empty grid, not an error page")
def test_search_without_matches(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()

    home.search("zzzzznosuchproduct")

    expect(home.product_cards).to_have_count(0)
    expect(home.no_results).to_be_visible()
    expect(home.result_count).to_contain_text("0 products found")


@allure.title("Resetting the search restores the full grid")
def test_search_reset(page: Page) -> None:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()
    original = home.product_cards.count()

    home.search("pliers")
    home.reset_search()

    expect(home.product_cards).to_have_count(original)
