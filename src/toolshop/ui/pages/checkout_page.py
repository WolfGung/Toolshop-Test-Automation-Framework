from __future__ import annotations

import allure
from playwright.sync_api import expect

from toolshop.config import settings
from toolshop.data.factories import GuestCustomer
from toolshop.ui.pages.base_page import BasePage


class CheckoutPage(BasePage):
    """Steps that follow the cart: sign-in choice, address, payment."""

    path = "/checkout"

    @allure.step("Continue as guest")
    def continue_as_guest(self, customer: GuestCustomer) -> None:
        expect(self.by_test("guest-email")).to_be_visible(timeout=settings.default_timeout)
        self.by_test("guest-email").fill(customer.email)
        self.by_test("guest-first-name").fill(customer.first_name)
        self.by_test("guest-last-name").fill(customer.last_name)
        self.by_test("guest-submit").click()

    @allure.step("Fill in the delivery address")
    def fill_address(self, customer: GuestCustomer) -> None:
        expect(self.by_test("street")).to_be_visible(timeout=settings.default_timeout)
        self.by_test("country").select_option(label=customer.country)
        self.by_test("postal_code").fill(customer.postal_code)
        self.by_test("house_number").fill(customer.house_number)
        self.by_test("street").fill(customer.street)
        self.by_test("city").fill(customer.city)
        self.by_test("state").fill(customer.state)
        self.by_test("proceed-3").click()

    @allure.step("Choose payment method '{method}'")
    def choose_payment(self, method: str = "Cash on Delivery") -> None:
        expect(self.by_test("payment-method")).to_be_visible(timeout=settings.default_timeout)
        self.by_test("payment-method").select_option(label=method)

    @allure.step("Confirm the order")
    def confirm(self) -> None:
        self.by_test("finish").click()
