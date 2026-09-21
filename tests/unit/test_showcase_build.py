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
