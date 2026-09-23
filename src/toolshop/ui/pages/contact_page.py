from __future__ import annotations

import allure
from playwright.sync_api import Locator, expect

from toolshop.config import settings
from toolshop.data.factories import ContactMessage
from toolshop.ui.pages.base_page import BasePage


#: One `alert-danger` banner per invalid field, in the order the fields
#: appear on the form. Older markup nested every message as a `<div>` inside
#: a single `data-test="message-error"` container; the application now
#: renders a separate, independently keyed container per field instead.
_ERROR_TEST_IDS = (
    "first-name-error",
    "last-name-error",
    "email-error",
    "subject-error",
    "message-error",
)


class ContactPage(BasePage):
    """Contact form.

    Validation is client-side: submitting an incomplete form renders one
    `alert-danger` banner per invalid field and sends no request.
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
        """The currently rendered per-field validation banners, in field order."""
        selector = ", ".join(f'[data-test="{test_id}"]' for test_id in _ERROR_TEST_IDS)
        return self.page.locator(selector)

    def error(self, field: str) -> Locator:
        """The validation banner of one field: ``first-name``, ``email``, ``message``…"""
        test_id = f"{field}-error"
        assert test_id in _ERROR_TEST_IDS, f"no validation banner for {field!r}"
        return self.by_test(test_id)

    @property
    def error_texts(self) -> list[str]:
        return [t.strip() for t in self.errors.all_inner_texts()]
