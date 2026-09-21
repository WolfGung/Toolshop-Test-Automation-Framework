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

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# The public run to show in the README screenshot. Repointed whenever a newer
# run on `main` is a better thing to show: the screenshot is read as "this is
# what the pipeline does", so the pinned run has to be a push to `main` whose
# title is a real commit subject and whose stand and publish jobs are both
# green. Check https://github.com/WolfGung/Toolshop-Test-Automation-Framework/
# actions?query=branch%3Amain before changing it.
CI_RUN_ID = "35620987841"

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


def _summary_statistic(page: Page, summary_url: str) -> dict[str, int]:
    """The overview's own numbers, or an explanation of why there are none.

    A half-generated report is the ordinary failure here: the directory looks
    like a report, the page even renders, but `widgets/summary.json` is
    missing, truncated or is the server's 404 page. Left alone that surfaces
    as a JSON decode error naming nothing, so every case is turned into a
    sentence that says what was found at that URL and what to do about it.
    """
    fix = (
        "Generate the report again before taking this screenshot:\n"
        "  ~/.local/bin/allure generate allure-results --clean -o site/report\n"
        "and serve it with `python -m http.server -d site 8899`."
    )
    response = page.request.get(summary_url)
    if not response.ok:
        raise RuntimeError(
            f"{summary_url} answered HTTP {response.status}, so the report "
            f"being photographed has no overview data. Either the report was "
            f"never generated into site/report, or the server is not serving "
            f"it.\n{fix}"
        )
    body = response.text()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{summary_url} is not JSON ({exc}); it starts with "
            f"{body[:120]!r}. That is what a half-written report, or a web "
            f"server answering with an HTML error page, looks like.\n{fix}"
        ) from exc
    statistic = parsed.get("statistic") if isinstance(parsed, dict) else None
    if not isinstance(statistic, dict):
        held = sorted(parsed) if isinstance(parsed, dict) else type(parsed).__name__
        raise RuntimeError(
            f"{summary_url} parsed, but it carries no 'statistic' object: it "
            f"is {len(body)} byte(s) holding {held}. A complete report always "
            f"has one.\n{fix}"
        )
    missing = sorted(
        key for key in ("total", "failed", "broken", "unknown")
        if not isinstance(statistic.get(key), int)
    )
    if missing:
        raise RuntimeError(
            f"{summary_url} reports a run without {', '.join(missing)}; its "
            f"statistic is {statistic}. The counts this screenshot is checked "
            f"against cannot be read from it.\n{fix}"
        )
    return statistic


def _require_report_is_complete_and_green(page: Page) -> None:
    """Refuse to screenshot a report that is partial or has failures.

    Waiting for the text "test cases" only proves *an* overview rendered —
    a five-test partial with two failures says "test cases" too. The overview
    is drawn straight from this JSON, so reading it is reading what a viewer
    of the screenshot would actually see: how many cases the run reports, and
    whether any of them failed.
    """
    summary_url = page.url.rstrip("/") + "/widgets/summary.json"
    stat = _summary_statistic(page, summary_url)
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
