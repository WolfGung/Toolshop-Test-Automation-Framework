from __future__ import annotations

import allure
from playwright.sync_api import expect

from toolshop.config import settings
from toolshop.ui.pages.base_page import BasePage


class ProductPage(BasePage):
    """Product detail page."""

    @property
    def name(self) -> str:
        return self.by_test("product-name").inner_text().strip()

    @property
    def unit_price(self) -> float:
        return float(self.by_test("unit-price").inner_text().replace("$", "").strip())

    def wait_for_loaded(self) -> None:
        expect(self.by_test("add-to-cart")).to_be_enabled(timeout=settings.default_timeout)

    @allure.step("Set quantity to {value}")
    def set_quantity(self, value: int) -> None:
        field = self.by_test("quantity")
        field.fill(str(value))

    @allure.step("Increase quantity {times} time(s)")
    def increase_quantity(self, times: int = 1) -> None:
        for _ in range(times):
            self.by_test("increase-quantity").click()

    @allure.step("Add product to cart")
    def add_to_cart(self) -> None:
        """Waits for the cart write to complete before returning.

        The button fires an asynchronous cart update; without waiting for the
        badge to settle the next assertion races the UI.
        """
        before = self.cart_quantity
        self.by_test("add-to-cart").click()
        expect(self.by_test("cart-quantity")).not_to_have_text(
            str(before), timeout=settings.default_timeout
        )
