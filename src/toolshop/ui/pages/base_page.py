"""Shared page behaviour.

Locators use the application's own `data-test` attributes. They are part of
the app's markup contract, so they survive copy and layout changes that would
break text or CSS-path selectors.
"""
from __future__ import annotations

import allure
from playwright.sync_api import Locator, Page, expect

from toolshop.config import settings


class BasePage:
    path: str = "/"

    def __init__(self, page: Page) -> None:
        self.page = page

    def open(self, path: str | None = None) -> None:
        target = f"{settings.base_url}{path or self.path}"
        with allure.step(f"Open {target}"):
            self.page.goto(target, wait_until="domcontentloaded")

    def by_test(self, test_id: str) -> Locator:
        return self.page.locator(f'[data-test="{test_id}"]')

    def expect_loaded(self, test_id: str) -> None:
        expect(self.by_test(test_id)).to_be_visible(timeout=settings.default_timeout)

    @property
    def cart_quantity(self) -> int:
        """0 when the badge is absent, which is how an empty cart renders."""
        badge = self.by_test("cart-quantity")
        if not badge.count():
            return 0
        text = (badge.inner_text() or "").strip()
        return int(text) if text.isdigit() else 0
