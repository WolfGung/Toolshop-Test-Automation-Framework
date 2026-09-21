"""The page reports the run it was built from, not numbers typed by hand."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showcase.build import build_site, summarise


def _result(tmp: Path, name: str, status: str, package: str, tags: list[str]) -> None:
    body = {
        "name": name,
        "status": status,
        "stop": 1_758_400_000_000,
        "labels": [{"name": "package", "value": package}]
        + [{"name": "tag", "value": t} for t in tags],
    }
    (tmp / f"{name}-result.json").write_text(json.dumps(body), encoding="utf-8")


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
    assert (summary.total, summary.product, summary.framework) == (5, 4, 1)


# What the page does with the artefacts that arrive later.

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
    assert (summary.total, summary.skipped) == (5, 1)
    assert summary.passed + summary.failed + summary.skipped + summary.unknown == 5
    assert "did not run: the suite skips a check" in _page(results, tmp_path)


def test_a_result_with_no_verdict_is_counted_as_unknown(results: Path) -> None:
    _result(results, "e", "unknown", "tests.ui.test_cart", ["ui"])
    summary = summarise(results)
    assert summary.unknown == 1
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
