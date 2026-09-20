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

    #: Rendered by the application on every page once it has booted.
    APP_SHELL = '[data-test="nav-home"]'

    def open(self, path: str | None = None) -> None:
        target = f"{settings.base_url}{path or self.path}"
        with allure.step(f"Open {target}"):
            response = self.page.goto(target, wait_until="load")
            self.wait_for_app(response)

    def wait_for_app(self, response: object | None = None) -> None:
        """Fail with the actual cause when the app does not render.

        Without this, a page that never booted surfaces as "element not
        found" on whichever locator the test happens to use first, which
        sends the reader hunting for a selector bug that is not there.
        """
        try:
            self.page.wait_for_selector(
                self.APP_SHELL, state="attached", timeout=settings.app_ready_timeout
            )
        except Exception as exc:  # noqa: BLE001 - re-raised with context
            status = getattr(response, "status", "unknown")
            root = self.page.locator("app-root").inner_html() if self.page.locator("app-root").count() else "<missing>"
            raise AssertionError(
                "The application shell never rendered at "
                f"{self.page.url} (navigation status: {status}). "
                f"app-root contained: {root[:200]!r}. "
                "The page was served but the single-page app did not boot — "
                "check whether the environment is reachable and not serving "
                "a bot challenge instead of the application."
            ) from exc

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
