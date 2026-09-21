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
        """Fill the guest panel and advance the wizard to the address step.

        "Continue as Guest" is now a tab alongside "Sign in", and "Sign in"
        is the one active by default, so `guest-email` exists in the DOM but
        stays hidden until the tab is selected. There is no `data-test` on
        the tab itself, so it is addressed by `href="#guest-tab"` — the
        tab's routing fragment, which Bootstrap's tab plugin uses to wire it
        to its panel — rather than by the "Continue as Guest" copy on it.
        The fragment is the part of the markup the panel actually depends
        on; the visible text is free to change under a copy edit the same
        way any other label on this page is, and a locator keyed on it
        would break with the copy rather than with the contract. Submitting
        the guest form then reveals a second, separate control —
        `proceed-2-guest` — that moves the wizard on to the address step;
        the form submit alone does not advance it.
        """
        self.page.locator('a[href="#guest-tab"]').click()
        expect(self.by_test("guest-email")).to_be_visible(timeout=settings.default_timeout)
        self.by_test("guest-email").fill(customer.email)
        self.by_test("guest-first-name").fill(customer.first_name)
        self.by_test("guest-last-name").fill(customer.last_name)
        self.by_test("guest-submit").click()
        expect(self.by_test("proceed-2-guest")).to_be_visible(timeout=settings.default_timeout)
        self.by_test("proceed-2-guest").click()

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
