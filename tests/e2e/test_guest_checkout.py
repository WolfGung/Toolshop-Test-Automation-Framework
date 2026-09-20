"""End-to-end guest checkout.

The suite walks the whole purchase path and stops before the order is placed.
Placing the order writes to a demo backend shared by everyone practising
against this site, so that last click lives in its own test behind the
`creates_data` marker, which pytest.ini deselects by default.
"""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from toolshop.data.factories import GuestCustomer
from toolshop.ui.pages.cart_page import CartPage
from toolshop.ui.pages.checkout_page import CheckoutPage
from toolshop.ui.pages.home_page import HomePage
from toolshop.ui.pages.product_page import ProductPage

pytestmark = [pytest.mark.e2e, allure.feature("Checkout")]


def _fill_cart(page: Page, quantity: int = 2) -> float:
    """Add one product with the given quantity and return the expected total."""
    home = HomePage(page)
    home.open()
    home.wait_for_catalog()
    home.open_product(0)

    detail = ProductPage(page)
    detail.wait_for_loaded()
    price = detail.unit_price
    detail.set_quantity(quantity)
    detail.add_to_cart()
    return round(price * quantity, 2)


@pytest.mark.smoke
@allure.title("A guest can reach the payment step with the correct order total")
def test_guest_reaches_payment_step(page: Page) -> None:
    expected_total = _fill_cart(page)
    customer = GuestCustomer()

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()
    assert cart.total == pytest.approx(expected_total, abs=0.01)
    cart.proceed()

    checkout = CheckoutPage(page)
    checkout.continue_as_guest(customer)
    checkout.fill_address(customer)
    checkout.choose_payment("Cash on Delivery")

    expect(checkout.by_test("finish")).to_be_enabled()


@pytest.mark.creates_data
@allure.title("A guest order can be placed end to end")
def test_guest_can_place_an_order(page: Page) -> None:
    _fill_cart(page, quantity=1)
    customer = GuestCustomer()

    cart = CartPage(page)
    cart.open()
    cart.wait_for_loaded()
    cart.proceed()

    checkout = CheckoutPage(page)
    checkout.continue_as_guest(customer)
    checkout.fill_address(customer)
    checkout.choose_payment("Cash on Delivery")
    checkout.confirm()

    expect(page.locator(".alert-success")).to_be_visible()
