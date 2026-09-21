"""The page reports the run it was built from, not numbers typed by hand."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from showcase.build import build_site, summarise


def _result(
    tmp: Path,
    name: str,
    status: str,
    package: str,
    tags: list[str],
    *,
    attempt: str = "",
    history: str | None = None,
    stop: int = 1_758_400_000_000,
    parameters: dict[str, str] | None = None,
) -> None:
    """One Allure result file, which is one *attempt* at a test.

    A rerun writes a second file for the same test, carrying the same
    ``historyId`` and a later ``stop``. ``attempt`` only names the file, so a
    test can write more than one without overwriting itself.
    """
    body = {
        "name": name,
        "fullName": f"{package}#{name}",
        "status": status,
        "stop": stop,
        "labels": [{"name": "package", "value": package}]
        + [{"name": "tag", "value": t} for t in tags],
    }
    if history is not None:
        body["historyId"] = history
    if parameters is not None:
        body["parameters"] = [{"name": k, "value": v} for k, v in parameters.items()]
    (tmp / f"{name}{attempt}-result.json").write_text(json.dumps(body), encoding="utf-8")


@pytest.fixture
def results(tmp_path: Path) -> Path:
    _result(tmp_path, "a", "passed", "tests.api.test_products_api", ["api", "smoke"])
    _result(tmp_path, "b", "passed", "tests.ui.test_cart", ["ui"])
    _result(tmp_path, "c", "failed", "tests.ui.test_search", ["ui", "smoke"])
    _result(tmp_path, "d", "passed", "tests.e2e.test_guest_checkout", ["e2e", "smoke"])
    (tmp_path / "unrelated.txt").write_text("ignored", encoding="utf-8")
    return tmp_path


def test_counts_by_status(results: Path) -> None:
    summary = summarise(results)
    assert (summary.total, summary.passed, summary.failed) == (4, 3, 1)


def test_counts_by_layer(results: Path) -> None:
    assert summarise(results).by_layer == {"api": 1, "ui": 2, "e2e": 1}


def test_counts_the_smoke_set(results: Path) -> None:
    assert summarise(results).smoke == 3


def test_empty_results_are_an_error_not_a_zero(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no Allure results"):
        summarise(tmp_path)


# The run also carries tests of the framework's own configuration, which are not
# checks of the product. The page has to add up, so the split is counted too.

def test_tests_without_a_layer_are_counted_apart_from_the_product(results: Path) -> None:
    _result(results, "e", "passed", "tests.unit.test_config", [])
    summary = summarise(results)
    assert (summary.total, summary.product.total, summary.framework.total) == (5, 4, 1)


# What the page does with the artefacts that arrive later.

def _prose(page: str) -> str:
    """The page's text with its line breaks collapsed, for asserting sentences."""
    return re.sub(r"\s+", " ", page)


def _page(results: Path, tmp_path: Path, **kwargs) -> str:
    out = tmp_path / "site"
    build_site(results, out, revision="0123456789abcdef", run_url="", **kwargs)
    return (out / "index.html").read_text(encoding="utf-8")


def test_no_placeholder_survives_the_build(results: Path, tmp_path: Path) -> None:
    assert "{{" not in _page(results, tmp_path)


def test_a_missing_recording_is_said_in_words_not_shown_as_a_black_box(
    results: Path, tmp_path: Path
) -> None:
    page = _page(results, tmp_path, video_dir=tmp_path / "nothing")
    assert "<video" not in page
    assert "recording" in page.lower()


def test_a_recording_that_exists_is_published_beside_the_page(
    results: Path, tmp_path: Path
) -> None:
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "guest-checkout-a.webm").write_bytes(b"x" * 20_000)
    out = tmp_path / "site"
    build_site(results, out, revision="abc1234", run_url="", video_dir=videos)
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "<video" in page
    assert (out / "media" / "checkout.webm").read_bytes() == b"x" * 20_000


def test_a_missing_run_url_leaves_no_empty_link(results: Path, tmp_path: Path) -> None:
    assert 'href=""' not in _page(results, tmp_path)


# A value that reaches the template is data, not markup. The revision and the
# run URL arrive from git and from the CI environment; neither is trusted.

def test_a_value_cannot_close_an_attribute_and_open_a_script(
    results: Path, tmp_path: Path
) -> None:
    out = tmp_path / "site"
    build_site(
        results, out,
        revision='abc1234"><script>alert(1)</script>',
        run_url='https://example.com/"><script>alert(2)</script>',
    )
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_a_run_url_that_is_not_a_link_is_dropped_rather_than_rendered(
    results: Path, tmp_path: Path
) -> None:
    out = tmp_path / "site"
    build_site(results, out, revision="abc1234", run_url="javascript:alert(1)")
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "javascript:" not in page
    assert "that produced them is public" not in page  # the whole block is gone


# Every result that is counted has to land somewhere a reader can see, or the
# page shows a total it cannot account for.

def test_a_skipped_result_is_counted_and_said_on_the_page(
    results: Path, tmp_path: Path
) -> None:
    _result(results, "e", "skipped", "tests.ui.test_cart", ["ui"])
    summary = summarise(results)
    assert (summary.total, summary.product.skipped) == (5, 1)
    assert (
        summary.product.passed + summary.product.failed
        + summary.product.skipped + summary.product.unknown
    ) == summary.product.total
    assert "did not run: the suite skips a check" in _prose(_page(results, tmp_path))


def test_a_result_with_no_verdict_is_counted_as_unknown(results: Path) -> None:
    _result(results, "e", "unknown", "tests.ui.test_cart", ["ui"])
    summary = summarise(results)
    assert summary.product.unknown == 1
    assert summary.passed + summary.failed + summary.skipped + summary.unknown == 5


def test_a_status_nobody_planned_for_stops_the_build(results: Path) -> None:
    _result(results, "e", "pending", "tests.ui.test_cart", ["ui"])
    with pytest.raises(ValueError, match="unrecognised Allure status"):
        summarise(results)


def test_a_case_at_two_layers_stops_the_build_instead_of_picking_one(
    results: Path,
) -> None:
    _result(results, "e", "passed", "tests.ui.test_cart", ["api", "ui"])
    with pytest.raises(ValueError, match="more than one layer tag"):
        summarise(results)


# The diagrams follow the same rule as the recording, in both directions.

def test_diagrams_that_exist_are_published_beside_the_page(
    results: Path, tmp_path: Path
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("architecture", "ci-pipeline"):
        (assets / f"{name}.svg").write_text(f"<svg>{name}</svg>", encoding="utf-8")
    out = tmp_path / "site"
    build_site(results, out, revision="abc1234", run_url="", assets_dir=assets)
    page = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/architecture.svg"' in page
    assert 'src="assets/ci-pipeline.svg"' in page
    assert (out / "assets" / "ci-pipeline.svg").read_text(encoding="utf-8")


def test_missing_diagrams_are_said_in_words_not_shown_as_broken_images(
    results: Path, tmp_path: Path
) -> None:
    page = _page(results, tmp_path, assets_dir=tmp_path / "nothing")
    assert 'src="assets/' not in page
    assert "diagrams ship with the published build" in page


def test_an_artefact_already_in_place_is_used_and_left_alone(
    results: Path, tmp_path: Path
) -> None:
    """The publish step may copy artefacts in before or after this runs."""
    out = tmp_path / "site"
    (out / "media").mkdir(parents=True)
    (out / "media" / "checkout.webm").write_bytes(b"already here")
    build_site(results, out, revision="abc1234", run_url="",
               video_dir=tmp_path / "nothing")
    assert "<video" in (out / "index.html").read_text(encoding="utf-8")
    assert (out / "media" / "checkout.webm").read_bytes() == b"already here"


# The page is about the storefront, so the figures it leads with are about the
# storefront. Tests of this builder are part of the same run and must not
# inflate them -- nor disappear.

@pytest.fixture
def results_with_plumbing(results: Path) -> Path:
    _result(results, "u1", "passed", "tests.unit.test_config", [])
    _result(results, "u2", "failed", "tests.unit.test_showcase_build", [])
    return results


def test_the_headline_figures_count_the_application_only(
    results_with_plumbing: Path,
) -> None:
    summary = summarise(results_with_plumbing)
    assert (summary.product.total, summary.product.passed, summary.product.failed) == (4, 3, 1)
    assert (summary.framework.total, summary.framework.not_passed) == (2, 1)
    assert summary.total == 6  # the run as a whole is still available


def test_the_headline_does_not_grow_when_the_framework_gains_tests(
    results: Path, tmp_path: Path
) -> None:
    before = _page(results, tmp_path)
    for n in range(5):
        _result(results, f"u{n}", "passed", "tests.unit.test_showcase_build", [])
    after = _page(results, tmp_path)
    assert "<b>4</b><span>checks of the application</span>" in before
    assert "<b>4</b><span>checks of the application</span>" in after


def test_a_failing_framework_test_is_stated_on_the_page(
    results_with_plumbing: Path, tmp_path: Path
) -> None:
    prose = _prose(_page(results_with_plumbing, tmp_path))
    assert "2 checks of the framework itself" in prose
    assert "1 of them did not pass" in prose
    assert "all of them passed" not in prose


def test_a_clean_framework_run_is_stated_as_such(results: Path, tmp_path: Path) -> None:
    _result(results, "u1", "passed", "tests.unit.test_config", [])
    prose = _prose(_page(results, tmp_path))
    assert "1 checks of the framework itself" in prose
    assert "all of them passed" in prose


def test_a_run_of_nothing_but_product_tests_says_nothing_about_plumbing(
    results: Path, tmp_path: Path
) -> None:
    assert "of the framework itself" not in _prose(_page(results, tmp_path))


def test_what_the_page_shows_adds_up_to_what_it_says_ran(
    results_with_plumbing: Path, tmp_path: Path
) -> None:
    """A reader who subtracts the figures must not find a gap."""
    _result(results_with_plumbing, "s1", "skipped", "tests.ui.test_cart", ["ui"])
    summary = summarise(results_with_plumbing)
    page = _page(results_with_plumbing, tmp_path)
    shown = summary.product.passed + summary.product.failed + summary.product.skipped \
        + summary.product.unknown
    assert shown == summary.product.total
    assert f"<b>{summary.product.total}</b><span>checks of the application" in page
    assert f"{summary.product.skipped} of the {summary.product.total} did not run" in _prose(page)
    assert f"run of {summary.total} results in all" in _prose(page)


# A rerun writes a second result file for the same test. Counting files would
# publish a total the report beside it contradicts, which is the one number
# this page cannot get wrong.

@pytest.fixture
def results_with_a_rerun(results: Path) -> Path:
    """Result `c` failed, was rerun by `--reruns 1`, and passed the second time."""
    _result(
        results, "c", "passed", "tests.ui.test_search", ["ui", "smoke"],
        attempt="-retry", history="c-history", stop=1_758_400_060_000,
    )
    # The first attempt, rewritten to carry the same history id as the rerun.
    _result(
        results, "c", "failed", "tests.ui.test_search", ["ui", "smoke"],
        history="c-history",
    )
    return results


def test_a_rerun_is_one_test_not_two(results_with_a_rerun: Path) -> None:
    summary = summarise(results_with_a_rerun)
    assert (summary.total, summary.passed, summary.failed) == (4, 4, 0)


def test_the_smoke_set_and_the_layers_count_a_rerun_once(
    results_with_a_rerun: Path,
) -> None:
    """They are counted from the same files, so they need the same grouping."""
    summary = summarise(results_with_a_rerun)
    assert summary.smoke == 3
    assert summary.by_layer == {"api": 1, "ui": 2, "e2e": 1}


def test_the_verdict_is_the_attempt_the_report_shows(results_with_a_rerun: Path) -> None:
    """Allure counts the last attempt; a page that disagreed would be wrong."""
    summary = summarise(results_with_a_rerun)
    assert (summary.product.passed, summary.product.failed) == (4, 0)


def test_a_test_that_only_passed_on_a_rerun_is_named_on_the_page(
    results_with_a_rerun: Path, tmp_path: Path
) -> None:
    assert summarise(results_with_a_rerun).product.flaky == 1
    assert "1 of them passed only on a second attempt" in _prose(
        _page(results_with_a_rerun, tmp_path)
    )


def test_a_clean_run_says_nothing_about_flakes(results: Path, tmp_path: Path) -> None:
    assert summarise(results).product.flaky == 0
    assert "second attempt" not in _prose(_page(results, tmp_path))


def test_attempts_group_by_name_and_parameters_when_there_is_no_history_id(
    tmp_path: Path,
) -> None:
    for attempt, status in (("-1", "failed"), ("-2", "passed")):
        _result(
            tmp_path, "x", status, "tests.ui.test_cart", ["ui"],
            attempt=attempt, stop=1_758_400_000_000 + int(attempt[-1]),
            parameters={"browser": "chromium"},
        )
    summary = summarise(tmp_path)
    assert (summary.total, summary.passed) == (1, 1)


def test_two_parameters_of_one_test_stay_two_tests(tmp_path: Path) -> None:
    """The grouping must not swallow a parametrised case into its sibling."""
    for browser in ("chromium", "firefox"):
        _result(
            tmp_path, "x", "passed", "tests.ui.test_cart", ["ui"],
            attempt=f"-{browser}", parameters={"browser": browser},
        )
    assert summarise(tmp_path).total == 2
