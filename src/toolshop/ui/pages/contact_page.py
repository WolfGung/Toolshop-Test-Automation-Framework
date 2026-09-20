from __future__ import annotations

import allure
from playwright.sync_api import Locator, expect

from toolshop.config import settings
from toolshop.data.factories import ContactMessage
from toolshop.ui.pages.base_page import BasePage


class ContactPage(BasePage):
    """Contact form.

    Validation is client-side: submitting an incomplete form renders messages
    inside an `.alert-danger` block and sends no request.
    """

    path = "/contact"

    def wait_for_loaded(self) -> None:
        expect(self.by_test("contact-submit")).to_be_visible(timeout=settings.default_timeout)

    @allure.step("Fill in the contact form")
    def fill(self, message: ContactMessage) -> None:
        self.by_test("first-name").fill(message.first_name)
        self.by_test("last-name").fill(message.last_name)
        self.by_test("email").fill(message.email)
        self.by_test("subject").select_option(label=message.subject)
        self.by_test("message").fill(message.message)

    @allure.step("Submit the contact form")
    def submit(self) -> None:
        self.by_test("contact-submit").click()

    @property
    def errors(self) -> Locator:
        """Individual validation messages inside the form's alert block."""
        return self.by_test("message-error").locator("div")

    @property
    def error_texts(self) -> list[str]:
        return [t.strip() for t in self.errors.all_inner_texts()]

    @property
    def alert(self) -> Locator:
        """The alert container itself, which carries role="alert"."""
        return self.by_test("message-error")
