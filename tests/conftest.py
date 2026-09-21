"""Shared fixtures.

Failure artefacts (screenshot, page HTML, console log) are attached to the
Allure report automatically, so a red test in CI can be diagnosed without
reproducing it locally.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import allure
import pytest
from playwright.sync_api import Page

from toolshop.api.client import ApiClient
from toolshop.api.products import CatalogApi, ProductsApi
from toolshop.config import settings


# --------------------------------------------------------------------- API

@pytest.fixture(scope="session")
def api_client() -> Iterator[ApiClient]:
    with ApiClient() as client:
        yield client


@pytest.fixture(scope="session")
def products_api(api_client: ApiClient) -> ProductsApi:
    return ProductsApi(api_client)


@pytest.fixture(scope="session")
def catalog_api(api_client: ApiClient) -> CatalogApi:
    return CatalogApi(api_client)


# ---------------------------------------------------------------- browser

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    return {
        **browser_type_launch_args,
        "headless": settings.headless,
        "slow_mo": settings.slow_mo,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    args = {
        **browser_context_args,
        "base_url": settings.base_url,
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-GB",
    }
    if settings.record_video:
        args["record_video_dir"] = settings.video_dir
        args["record_video_size"] = {"width": 1440, "height": 900}
    return args


@pytest.fixture(autouse=True)
def _page_defaults(request: pytest.FixtureRequest) -> Iterator[None]:
    """Apply timeouts and collect console errors for browser tests only."""
    if "page" not in request.fixturenames:
        yield
        return

    page: Page = request.getfixturevalue("page")
    page.set_default_timeout(settings.default_timeout)
    console: list[str] = []
    page.on("console", lambda msg: console.append(f"{msg.type}: {msg.text}")
            if msg.type in {"error", "warning"} else None)
    request.node.stash_console = console  # type: ignore[attr-defined]
    yield


@pytest.fixture(autouse=True)
def _attach_video(request: pytest.FixtureRequest) -> Iterator[None]:
    """Keep the checkout recording and discard every other video.

    ``record_video_dir`` is a session-scoped context option, so once it is
    set every browser test is recorded, not only the one that gets
    published. Only the ``e2e`` checkout flow is meant to become the
    showcase video, so this fixture renames that recording to a predictable
    path and deletes the rest as soon as each test ends, rather than leaving
    a later step to guess which file is the right one (e.g. by picking the
    largest).

    The ``page`` fixture is fetched *before* the ``yield``, exactly like
    ``_page_defaults`` above: that is what keeps it alive across teardown.
    Fetching it after the ``yield`` instead -- reading ``request.fixturenames``
    is not enough on its own -- races the ``context``/``page`` fixtures' own
    teardown in this pytest-playwright version and raises "fixture value for
    'page' is not available"; this fixture must run, and close the page,
    before that teardown happens, since Playwright only flushes the video
    file on close.
    """
    if not settings.record_video or "page" not in request.fixturenames:
        yield
        return
    page: Page = request.getfixturevalue("page")
    yield
    try:
        video = page.video
        if video is None:
            return
        page.close()
        recorded = Path(video.path())
        if request.node.get_closest_marker("e2e") is None:
            recorded.unlink(missing_ok=True)
            return
        kept = Path(settings.video_dir) / f"guest-checkout-{request.node.name}.webm"
        recorded.replace(kept)
        allure.attach.file(
            str(kept), name="video",
            attachment_type=allure.attachment_type.WEBM,
        )
    except Exception:  # a recording is never worth failing a green test over
        pass


class SubmittedRequests(list):
    """Captured POST bodies, so a test can assert what the app actually sent."""


@pytest.fixture
def mock_contact_api(page: Page) -> Iterator[SubmittedRequests]:
    """Record what the application sent, in both modes.

    The backend is a shared instance used by everyone practising against this
    site. A test that only needs to prove the form posts the right payload
    should not add noise to it, so POSTs are answered locally there and
    captured. Set MOCK_CONTACT_API=false to exercise the real endpoint
    instead: the request still reaches the application, and it is still
    captured, but the fixture only answers on the backend's behalf when the
    backend is somebody else's.
    """
    captured = SubmittedRequests()

    def _matcher(url: object) -> bool:
        return settings.api_base_url in str(url)

    def _record(route) -> None:  # type: ignore[no-untyped-def]
        request = route.request
        if request.method != "POST":
            route.fallback()
            return
        captured.append({"url": request.url, "body": request.post_data_json})
        if settings.mock_contact_api:
            route.fulfill(status=200, content_type="application/json", body="{}")
        else:
            route.continue_()

    page.route(_matcher, _record)
    yield captured
    page.unroute(_matcher, _record)


# ------------------------------------------------------------- reporting

@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    page = item.funcargs.get("page")
    if page is None:
        return

    try:
        allure.attach(
            page.screenshot(full_page=True),
            name="screenshot",
            attachment_type=allure.attachment_type.PNG,
        )
        allure.attach(page.content(), name="page.html",
                      attachment_type=allure.attachment_type.HTML)
        allure.attach(page.url, name="url",
                      attachment_type=allure.attachment_type.TEXT)
    except Exception:  # the page may already be closed
        pass

    console = getattr(item, "stash_console", None)
    if console:
        allure.attach("\n".join(console), name="console",
                      attachment_type=allure.attachment_type.TEXT)


def pytest_configure(config: pytest.Config) -> None:
    try:
        configured = config.getoption("--alluredir")
    except ValueError:  # allure-pytest not installed
        configured = None
    results = Path(configured or "allure-results")
    results.mkdir(parents=True, exist_ok=True)
    (results / "environment.properties").write_text(
        "\n".join(
            [
                f"BASE_URL={settings.base_url}",
                f"API_BASE_URL={settings.api_base_url}",
                f"Headless={settings.headless}",
                f"Python={sys.version.split()[0]}",
                f"MockContactApi={settings.mock_contact_api}",
                f"CI={os.getenv('CI', 'false')}",
            ]
        ),
        encoding="utf-8",
    )
