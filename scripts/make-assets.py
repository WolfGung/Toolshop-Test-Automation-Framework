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
    ~/.local/bin/allure generate allure-results --clean -o site/report
    python -m http.server -d site 8899 &
    PYTHONPATH=. python scripts/make-assets.py
    kill %1
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# The public run to show in the README screenshot. Repointed once there is a
# green run on `main` worth showing instead — the run currently pinned here
# is a temporary branch trigger used to validate this pipeline, and its title
# ("Temporarily trigger CI on pushes to showcase…") will look odd once this
# branch has merged.
CI_RUN_ID = "35592623127"

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
        f"https://github.com/WolfGung/Toolshop-Test-Automation-Framework/actions/runs/{CI_RUN_ID}",
        "ci-screenshot.png",
        "text=Total duration",
        1536,
        1024,
    ),
]


def _collected_test_count() -> int:
    """How many tests pytest collects for the whole suite right now.

    Runs in a subprocess with its own throwaway allure directory: pytest.ini
    points every invocation at ``allure-results`` and cleans it on start, and
    collecting in-process here would wipe the results the report was just
    built from.
    """
    with tempfile.TemporaryDirectory() as spool:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", f"--alluredir={spool}", "-m", "",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    ids = [
        line for line in proc.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    if not ids:
        raise RuntimeError(
            f"pytest --collect-only collected nothing, so the report cannot be "
            f"checked against it.\n{proc.stdout}\n{proc.stderr}"
        )
    return len(ids)


def _require_report_is_complete_and_green(page: Page) -> None:
    """Refuse to screenshot a report that is partial or has failures.

    Waiting for the text "test cases" only proves *an* overview rendered —
    a five-test partial with two failures says "test cases" too. The overview
    is drawn straight from this JSON, so reading it is reading what a viewer
    of the screenshot would actually see: how many cases the run reports, and
    whether any of them failed.
    """
    summary_url = page.url.rstrip("/") + "/widgets/summary.json"
    stat = page.request.get(summary_url).json()["statistic"]
    not_green = stat["failed"] + stat["broken"] + stat["unknown"]
    expected = _collected_test_count()
    assert not_green == 0 and stat["total"] == expected, (
        f"site/report/ is not a complete, passing run: it reports "
        f"{stat['total']} test case(s) ({expected} expected from the current "
        f"suite), {stat['failed']} failed, {stat['broken']} broken, "
        f"{stat['unknown']} unknown. Regenerate it before taking this "
        f"screenshot: run the full suite, then `~/.local/bin/allure generate "
        f"allure-results --clean -o site/report`."
    )


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
            if name == "allure-report-screenshot.png":
                _require_report_is_complete_and_green(page)
            page.wait_for_timeout(3000)
            page.screenshot(path=ROOT / name)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
