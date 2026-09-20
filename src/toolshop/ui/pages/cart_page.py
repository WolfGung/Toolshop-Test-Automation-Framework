from __future__ import annotations

import allure
from playwright.sync_api import Locator, expect

from toolshop.config import settings
from toolshop.ui.pages.base_page import BasePage


class CartPage(BasePage):
    """Cart step of the checkout page."""

    path = "/checkout"

    @property
    def rows(self) -> Locator:
        return self.page.locator("tbody tr")

    @property
    def titles(self) -> list[str]:
        return [t.strip() for t in self.by_test("product-title").all_inner_texts()]

    def wait_for_loaded(self) -> None:
        expect(self.by_test("proceed-1")).to_be_visible(timeout=settings.default_timeout)

    @staticmethod
    def _money(text: str) -> float:
        return float(text.replace("$", "").replace(",", "").strip())

    def line_price(self, index: int = 0) -> float:
        return self._money(self.by_test("line-price").nth(index).inner_text())

    def unit_price(self, index: int = 0) -> float:
        return self._money(self.by_test("product-price").nth(index).inner_text())

    @property
    def total(self) -> float:
        return self._money(self.by_test("cart-total").inner_text())

    def quantity(self, index: int = 0) -> int:
        return int(self.by_test("product-quantity").nth(index).input_value())

    @allure.step("Set quantity of row {index} to {value}")
    def set_quantity(self, value: int, index: int = 0) -> None:
        field = self.by_test("product-quantity").nth(index)
        field.fill(str(value))
        # The row total is recalculated on blur, not on keystroke.
        field.press("Tab")

    @allure.step("Remove row {index} from the cart")
    def remove_row(self, index: int = 0) -> None:
        count_before = self.rows.count()
        self.rows.nth(index).locator("a.btn-danger").click()
        expect(self.rows).to_have_count(count_before - 1, timeout=settings.default_timeout)

    @allure.step("Proceed to checkout")
    def proceed(self) -> None:
        self.by_test("proceed-1").click()
