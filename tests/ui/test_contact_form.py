"""Contact form: validation and submission."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from toolshop.data.factories import ContactMessage
from toolshop.ui.pages.contact_page import ContactPage

pytestmark = [pytest.mark.ui, allure.feature("Contact form")]

REQUIRED_FIELD_ERRORS = [
    "First name is required",
    "Last name is required",
    "Email is required",
    "Subject is required",
    "Message is required",
]

MIN_MESSAGE_LENGTH = 50
MIN_LENGTH_ERROR = "Message must be minimal 50 characters"


@pytest.mark.smoke
@pytest.mark.negative
@allure.title("Submitting an empty form reports every required field")
def test_empty_form_reports_all_required_fields(page: Page) -> None:
    contact = ContactPage(page)
    contact.open()
    contact.wait_for_loaded()

    contact.submit()

    # The banners render one per field, not all in one paint: on a slow
    # storefront a read taken as soon as the first one shows sees one or two.
    # `to_have_text` on the list keeps looking until every banner is there.
    expect(contact.errors).to_have_text(REQUIRED_FIELD_ERRORS)


@pytest.mark.negative
@pytest.mark.parametrize(
    "invalid_email",
    ["plainaddress", "missing-at.example.com", "no-domain@", "@example.com"],
    ids=["no-at-symbol", "no-at", "no-domain", "no-local-part"],
)
@allure.title("A malformed address is rejected: {invalid_email}")
def test_invalid_email_is_rejected(page: Page, invalid_email: str) -> None:
    contact = ContactPage(page)
    contact.open()
    contact.wait_for_loaded()

    contact.fill(ContactMessage(email=invalid_email))
    contact.submit()

    expect(contact.error("email")).to_contain_text("Email")


@pytest.mark.negative
@pytest.mark.boundary
@allure.title("A message one character below the minimum is rejected")
def test_message_just_below_minimum(page: Page) -> None:
    contact = ContactPage(page)
    contact.open()
    contact.wait_for_loaded()

    contact.fill(ContactMessage(message="x" * (MIN_MESSAGE_LENGTH - 1)))
    contact.submit()

    expect(contact.error("message")).to_have_text(MIN_LENGTH_ERROR)


@pytest.mark.boundary
@allure.title("A message exactly at the minimum is accepted")
def test_message_at_minimum(page: Page, mock_contact_api) -> None:
    contact = ContactPage(page)
    contact.open()
    contact.wait_for_loaded()

    contact.fill(ContactMessage(message="x" * MIN_MESSAGE_LENGTH))
    contact.submit()

    expect(contact.errors).to_have_count(0)


@pytest.mark.smoke
@allure.title("A complete form posts the values the user entered")
def test_valid_submission_sends_entered_values(page: Page, mock_contact_api) -> None:
    contact = ContactPage(page)
    contact.open()
    contact.wait_for_loaded()
    message = ContactMessage()

    contact.fill(message)
    contact.submit()

    expect(contact.errors).to_have_count(0)
    assert mock_contact_api, "the form did not send a request"

    body = mock_contact_api[-1]["body"] or {}
    assert body.get("email") == message.email
    assert body.get("message") == message.message
