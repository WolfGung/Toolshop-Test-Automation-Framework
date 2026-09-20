"""Cart behaviour: adding, updating quantity, removing."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page

from toolshop.ui.pages.cart_page import CartPage
from toolshop.ui.pages.home_page import HomePage
from toolshop.ui.pages.product_page import ProductPage

pytestmark = [pytest.mark.ui, allure.feature("Cart")]


def _add_first_product(page: Page, quantity: int = 1) -> tuple[str, float]:
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()
    home.open_product(0)

    detail = ProductPage(page)
    detail.wait_for_loaded()
    name, price = detail.name, detail.unit_price
    if quantity > 1:
        detail.set_quantity(quantity)
    detail.add_to_cart()
    return name, price


@pytest.mark.smoke
@allure.title("A product added from the detail page appears in the cart")
def test_add_product_to_cart(page: Page) -> None:
    name, price = _add_first_product(page)

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()

    assert cart.titles == [name]
    assert cart.unit_price() == price
    assert cart.quantity() == 1
    assert cart.total == price


@allure.title("The line total follows the quantity chosen on the product page")
def test_quantity_is_carried_into_the_cart(page: Page) -> None:
    _, price = _add_first_product(page, quantity=3)

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()

    assert cart.quantity() == 3
    assert cart.line_price() == pytest.approx(price * 3, abs=0.01)
    assert cart.total == pytest.approx(price * 3, abs=0.01)


@allure.title("Changing the quantity in the cart recalculates the total")
def test_update_quantity_in_cart(page: Page) -> None:
    _, price = _add_first_product(page)

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()
    cart.set_quantity(2)

    assert cart.quantity() == 2
    assert cart.total == pytest.approx(price * 2, abs=0.01)


@allure.title("Removing the only line empties the cart")
def test_remove_product_from_cart(page: Page) -> None:
    _add_first_product(page)

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()
    cart.remove_row()

    assert cart.rows.count() == 0
