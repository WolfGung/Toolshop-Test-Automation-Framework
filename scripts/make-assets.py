"""Render the portfolio images from their sources.

Editing the wording on a cover should be editing a line of text, not opening an
image editor, so the cover is HTML and this script is the exporter. The two
screenshots come from the real thing — a generated Allure report served over
HTTP, and the public Actions page of this repository — so refreshing them is
re-running this script rather than letting them age into a lie.

The profile banner is not rendered here. It is a profile-level asset, identical
across the owner's projects, and it is committed as `guru-profile-banner-
1000x250.png`: a second banner that almost matched the first would look wrong
beside it in the same profile.

Usage:
    python -m http.server -d site 8899 &
    PYTHONPATH=. python scripts/make-assets.py
    kill %1
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# Sized to what the profile expects; anything else is cropped by it.
SHOTS = [
    ("showcase/assets/cover.html", "guru-cover-image.png", 1536, 1024),
]

# Both pages finish themselves after load: Allure draws the overview charts in
# script, and the GitHub run page fills its job list in. So each one waits for
# something it only shows when it is ready, then gets a moment to settle.
#
# `networkidle` is not usable here — GitHub holds a live connection open on the
# run page and never goes idle, so waiting for idle only ever times out.
PAGES = [
    (
        "http://localhost:8899/report/",
        "allure-report-screenshot.png",
        "text=test cases",
        1536,
        1024,
    ),
    (
        "https://github.com/WolfGung/Toolshop-Test-Automation-Framework/actions/runs/35592623127",
        "ci-screenshot.png",
        "text=Total duration",
        1536,
        1024,
    ),
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for source, name, width, height in SHOTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto((ROOT / source).as_uri())
            page.wait_for_timeout(300)
            page.screenshot(path=ROOT / name)
            page.close()
        for url, name, ready, width, height in PAGES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="load", timeout=60_000)
            page.wait_for_selector(ready, timeout=60_000)
            page.wait_for_timeout(3000)
            page.screenshot(path=ROOT / name)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
