from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import allure
from playwright.sync_api import Locator, expect

from toolshop.config import settings
from toolshop.ui.pages.base_page import BasePage


class HomePage(BasePage):
    """Catalog landing page: product grid, search, sorting, filters."""

    path = "/"

    @property
    def product_cards(self) -> Locator:
        return self.page.locator("a.card")

    @property
    def product_names(self) -> list[str]:
        return [n.strip() for n in self.by_test("product-name").all_inner_texts()]

    @property
    def product_prices(self) -> list[float]:
        raw = self.by_test("product-price").all_inner_texts()
        return [float(value.replace("$", "").replace(",", "").strip()) for value in raw]

    def wait_for_catalog(self) -> None:
        expect(self.product_cards.first).to_be_visible(timeout=settings.default_timeout)

    def grid_signature(self) -> str:
        """Order-sensitive fingerprint of the rendered grid."""
        return "|".join(self.product_names)

    @contextmanager
    def wait_for_products(self) -> Iterator[None]:
        """Block until the grid has been refetched *and* re-rendered.

        Sorting, searching and filtering all re-request the product list.
        Waiting on the response alone still races the render, so the grid
        fingerprint is watched afterwards. Every caller below changes the
        visible order or contents, so the fingerprint is guaranteed to move.
        """
        before = self.grid_signature()
        with self.page.expect_response(
            lambda r: "/products" in r.url and r.request.method == "GET" and r.ok,
            timeout=settings.default_timeout,
        ):
            yield
        self.page.wait_for_function(
            """(sig) => Array.from(
                   document.querySelectorAll('[data-test=\"product-name\"]')
               ).map(e => e.textContent.trim()).join('|') !== sig""",
            arg=before,
            timeout=settings.default_timeout,
        )

    @allure.step("Search for '{query}'")
    def search(self, query: str) -> None:
        self.by_test("search-query").fill(query)
        with self.wait_for_products():
            self.by_test("search-submit").click()

    @allure.step("Reset search")
    def reset_search(self) -> None:
        with self.wait_for_products():
            self.by_test("search-reset").click()

    @allure.step("Sort by '{option}'")
    def sort_by(self, option: str) -> None:
        with self.wait_for_products():
            self.by_test("sort").select_option(label=option)

    @property
    def no_results(self) -> Locator:
        return self.by_test("no-results")

    @property
    def result_count(self) -> Locator:
        return self.by_test("search-result-count")

    def open_product(self, index: int = 0) -> None:
        self.product_cards.nth(index).click()
