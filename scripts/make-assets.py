"""Render the portfolio images from their sources.

Editing the wording on a cover should be editing a line of text, not opening an
image editor, so the cover is HTML and this script is the exporter. The report
screenshot comes from the real thing, a generated Allure report served over
HTTP, so refreshing it is re-running this script instead of letting it age
into a lie. The picture of a CI run is that idea pointed at GitHub: it is
photographed from the public run page, and only once the API and the page
itself both say the run finished green.

The profile banner is not rendered here. It is a profile-level asset, identical
across the owner's projects, and it is committed as `guru-profile-banner-
1000x250.png`: a second banner that almost matched the first would look wrong
beside it in the same profile.

Usage:
    ~/.local/bin/allure generate allure-results --clean -o site/report
    python -m http.server -d site 8899 &
    PYTHONPATH=. python scripts/make-assets.py
    kill %1

    # Only the picture of CI: no report to generate, nothing to serve.
    PYTHONPATH=. python scripts/make-assets.py --ci-run
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# Sized to what the profile expects; anything else is cropped by it.
SHOTS = [
    ("showcase/assets/cover.html", "guru-cover-image.png", 1536, 1024),
]

# The report finishes itself after load: Allure draws the overview charts in
# script. So the page waits for something it only shows once it is ready, then
# gets a moment to settle.
PAGES = [
    (
        "http://localhost:8899/report/",
        "allure-report-screenshot.png",
        "text=test cases",
        1536,
        1024,
    ),
]

#: The repository whose runs may be photographed, its gate workflow, and the
#: branch that workflow gates. A run page from anywhere else is refused: the
#: picture is captioned as this project's CI, so it has to be this project's.
REPO = "WolfGung/Toolshop-Test-Automation-Framework"
WORKFLOW_FILE = "tests.yml"
BRANCH = "main"
GITHUB_API = "https://api.github.com"

#: Where the run page's picture lands, and how wide the browser is while it is
#: taken. 1400 is wide enough for GitHub to lay the page out as a desktop
#: reader sees it — the job list beside the graph rather than stacked under it.
CI_RUN_SHOT = "showcase/images/ci-run.png"
CI_VIEWPORT = (1400, 900)

#: The crop. The picture starts at the repository header, so it shows which
#: repository this is, and ends under the job graph: everything below is
#: annotations and artefact names, which say nothing a reader came for. The
#: marketing bar above the header is left out for the same reason.
CI_CROP_TOP = "#repository-container-header"
CI_CROP_BOTTOM = "[class*='WorkflowGraph']"
CI_CROP_PADDING = 16

#: A run page URL, as GitHub writes it in the address bar.
RUN_PAGE = re.compile(
    r"^https://github\.com/(?P<repo>[^/]+/[^/]+)/actions/runs/(?P<run>\d+)"
)

#: What `--ci-run` means with no URL after it: go and find one.
LATEST_GREEN = "latest-green"

#: The verdict the run page states in words, read back out of the rendered
#: page: the "Status" label and the value under it. Reading the page rather
#: than trusting the API is the point — it is the page that gets photographed,
#: and a reader believes what the picture shows, not what an endpoint said.
STATUS_ON_THE_PAGE = """() => {
  const label = Array.from(document.querySelectorAll('*')).find(
    (el) => el.children.length === 0 && (el.textContent || '').trim() === 'Status'
  );
  if (!label || !label.parentElement) return null;
  const lines = (label.parentElement.innerText || '')
    .split('\\n')
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length > 1 ? lines[lines.length - 1] : null;
}"""

#: The crop rectangle, in page coordinates, or null when the page no longer
#: has the two landmarks it is measured from.
CROP_ON_THE_PAGE = """({ top, bottom, padding }) => {
  const head = document.querySelector(top);
  const tail = document.querySelector(bottom);
  if (!head || !tail) return null;
  const from = head.getBoundingClientRect().top + window.scrollY;
  const to = tail.getBoundingClientRect().bottom + window.scrollY + padding;
  const width = document.documentElement.clientWidth;
  const height = Math.min(to, document.documentElement.scrollHeight) - from;
  return height > 0 ? { x: 0, y: from, width, height } : null;
}"""


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


def _github(path: str) -> dict:
    """One unauthenticated GET against the public API, or a sentence about why not.

    The repository is public and so are its runs, so no token is involved and
    none is wanted: anybody reading the README can repeat this call. What that
    costs is the anonymous rate limit, which is the one failure worth naming
    in the message, because it looks like nothing else and waiting fixes it.
    """
    url = f"{GITHUB_API}{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{REPO} make-assets",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()[:200]
        rate = (
            " That is what the anonymous rate limit looks like (60 requests an "
            "hour from one address); it clears by itself."
            if exc.code in (403, 429)
            else ""
        )
        raise RuntimeError(
            f"{url} answered HTTP {exc.code}, so which run to photograph "
            f"cannot be decided.{rate}\n{detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"{url} could not be reached ({exc.reason}). The run page and this "
            f"API are both public, so this is a network problem, not an access "
            f"one."
        ) from exc


def _current_main() -> str | None:
    """The commit `origin/main` points at, when this is a clone that knows it."""
    proc = subprocess.run(
        ["git", "rev-parse", f"origin/{BRANCH}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def _is_green(run: dict) -> bool:
    return run.get("status") == "completed" and run.get("conclusion") == "success"


def _latest_green_run() -> dict:
    """The run to photograph when no URL was given.

    The one for the commit `origin/main` is on is preferred, because the
    README beside the picture describes that commit's suite. A push whose run
    is still going is the ordinary case, though, so the newest green run is
    the fallback — with a line saying so, since the difference matters to
    whoever is about to commit the image.
    """
    payload = _github(
        f"/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs"
        f"?branch={BRANCH}&status=success&per_page=20"
    )
    runs = [run for run in payload.get("workflow_runs", []) if _is_green(run)]
    if not runs:
        raise RuntimeError(
            f"{REPO} has no completed, successful run of {WORKFLOW_FILE} on "
            f"{BRANCH} to photograph. Nothing is wrong with this script: there "
            f"is no green run to show yet."
        )
    runs.sort(
        key=lambda run: run.get("run_started_at") or run.get("created_at") or "",
        reverse=True,
    )
    head = _current_main()
    for run in runs:
        if head and run.get("head_sha") == head:
            return run
    newest = runs[0]
    if head:
        print(
            f"No green run of {WORKFLOW_FILE} for {BRANCH} at {head[:7]} yet — "
            f"photographing the newest green one instead: #{newest.get('run_number')} "
            f"at {str(newest.get('head_sha'))[:7]}.",
            file=sys.stderr,
        )
    return newest


def _named_run(url: str) -> dict:
    """The run a URL names, read back from the API so it can be checked."""
    match = RUN_PAGE.match(url.strip())
    if not match:
        raise RuntimeError(
            f"{url!r} is not a run page. It should look like "
            f"https://github.com/{REPO}/actions/runs/<id>, or be left off "
            f"entirely to take the latest green run."
        )
    if match.group("repo") != REPO:
        raise RuntimeError(
            f"{url} belongs to {match.group('repo')}, not {REPO}. The picture "
            f"is captioned as this project's CI, so it has to be this "
            f"project's run."
        )
    return _github(f"/repos/{REPO}/actions/runs/{match.group('run')}")


def _require_the_run_is_green(run: dict) -> None:
    """Refuse to photograph anything but a finished, green run of the gate.

    A picture is read as evidence, so each claim the caption makes is checked
    before the shutter: the run is over, it passed, it is this workflow, and
    it ran on the branch the README talks about. A run still in progress is
    the easy mistake — its page looks almost the same, with a spinner where
    the green check goes, and the jobs it has not started yet look skipped.
    """
    problems = []
    if run.get("status") != "completed":
        problems.append(f"it is {run.get('status')!r}, not finished")
    if run.get("conclusion") != "success":
        problems.append(f"it concluded {run.get('conclusion')!r}, not 'success'")
    if run.get("head_branch") != BRANCH:
        problems.append(f"it ran on {run.get('head_branch')!r}, not {BRANCH!r}")
    path = run.get("path") or ""
    if not path.endswith(WORKFLOW_FILE):
        problems.append(f"it is {path!r}, not the {WORKFLOW_FILE} workflow")
    if problems:
        raise RuntimeError(
            f"{run.get('html_url', 'that run')} is not a picture worth "
            f"committing: {'; '.join(problems)}.\nRun `python "
            f"scripts/make-assets.py --ci-run` with no URL to take the latest "
            f"completed green run of {WORKFLOW_FILE} on {BRANCH}."
        )


def _require_the_page_says_it_too(page: Page, run: dict) -> None:
    """Refuse unless the rendered page itself shows this run, green.

    The API answered about a run id; this is the page a viewer of the picture
    would read. Three things have to line up on it, and they are exactly what
    the picture shows: the run number, so the page is not some other run or a
    sign-in wall, the workflow file, and the word under "Status".
    """
    try:
        page.wait_for_function(STATUS_ON_THE_PAGE, timeout=60_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            f"{page.url} never rendered a 'Status' with a verdict under it, so "
            f"there is no way to check that the page shows what this picture "
            f"claims. Either the page did not load, or GitHub has changed the "
            f"run page and STATUS_ON_THE_PAGE has to change with it."
        ) from None
    shown = page.evaluate(STATUS_ON_THE_PAGE)
    if shown != "Success":
        raise RuntimeError(
            f"{page.url} shows its status as {shown!r}, not 'Success'. The "
            f"API called this run {run.get('conclusion')!r}, so the two "
            f"disagree — the picture is not taken either way."
        )
    body = page.inner_text("body")
    for expected, what in (
        (f"#{run.get('run_number')}", "the run number"),
        (WORKFLOW_FILE, "the workflow file"),
    ):
        if expected not in body:
            raise RuntimeError(
                f"{page.url} does not show {what} ({expected!r}), so it is not "
                f"the page this picture is supposed to be of."
            )


def _crop(page: Page) -> dict[str, float] | None:
    """The rectangle worth keeping, or nothing when the page changed shape."""
    return page.evaluate(
        CROP_ON_THE_PAGE,
        {"top": CI_CROP_TOP, "bottom": CI_CROP_BOTTOM, "padding": CI_CROP_PADDING},
    )


def _photograph_the_ci_run(browser, where: str) -> None:
    """Write showcase/images/ci-run.png from a public GitHub Actions run page."""
    run = _latest_green_run() if where == LATEST_GREEN else _named_run(where)
    _require_the_run_is_green(run)

    width, height = CI_VIEWPORT
    page = browser.new_page(viewport={"width": width, "height": height})
    try:
        page.goto(run["html_url"], wait_until="domcontentloaded", timeout=60_000)
        _require_the_page_says_it_too(page, run)
        try:
            page.wait_for_selector(CI_CROP_BOTTOM, timeout=30_000)
        except PlaywrightTimeout:
            print(
                f"The job graph did not render on {page.url}; the picture will "
                f"be the visible page instead of a crop.",
                file=sys.stderr,
            )
        # The job verdict icons and the durations arrive after the graph does.
        page.wait_for_timeout(2000)
        target = ROOT / CI_RUN_SHOT
        target.parent.mkdir(parents=True, exist_ok=True)
        crop = _crop(page)
        page.screenshot(path=target, **({"clip": crop} if crop else {}))
        print(
            f"{CI_RUN_SHOT}: {WORKFLOW_FILE} run #{run.get('run_number')} on "
            f"{BRANCH} at {str(run.get('head_sha'))[:7]} — {run['html_url']}"
        )
    finally:
        page.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Which pictures to make. With no options: the two local ones, as before.

    The CI picture is kept off that default on purpose. It is the only one
    that needs the network, and the only one whose source is someone else's
    site, so an export of the cover should not fail because GitHub was slow.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog=(
            "With no options, the cover and the Allure report screenshot are "
            "made, which needs the report generated and served first (see the "
            "module docstring)."
        ),
    )
    parser.add_argument(
        "--cover",
        action="store_true",
        help="render showcase/assets/cover.html to guru-cover-image.png",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help=(
            "photograph the Allure report served at "
            f"{PAGES[0][0]}; refuses a partial or failing report"
        ),
    )
    parser.add_argument(
        "--ci-run",
        nargs="?",
        const=LATEST_GREEN,
        metavar="URL",
        help=(
            f"photograph a run page into {CI_RUN_SHOT}; with no URL, the "
            f"latest completed green run of {WORKFLOW_FILE} on {BRANCH}, "
            f"preferring the one for the commit origin/{BRANCH} points at. "
            f"A run that is not green is refused"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    asked = args.cover or args.report or args.ci_run is not None
    cover = args.cover or not asked
    report = args.report or not asked

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            if cover:
                for source, name, width, height in SHOTS:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto((ROOT / source).as_uri())
                    page.wait_for_timeout(300)
                    page.screenshot(path=ROOT / name)
                    page.close()
            if report:
                for url, name, ready, width, height in PAGES:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(url, wait_until="load", timeout=60_000)
                    page.wait_for_selector(ready, timeout=60_000)
                    if name == "allure-report-screenshot.png":
                        _require_report_is_complete_and_green(page)
                    page.wait_for_timeout(3000)
                    page.screenshot(path=ROOT / name)
                    page.close()
            if args.ci_run is not None:
                _photograph_the_ci_run(browser, args.ci_run)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
