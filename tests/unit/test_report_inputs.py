"""What a run has to leave in its results directory for the report to say it.

Allure builds the Environment panel and the Categories tab out of two files it
expects to find among the results, and `allure generate` takes neither as a
flag. Both were promised in the README long before one of them was written,
which is the failure these tests exist to prevent: the claim is checked where
the file is produced.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import CATEGORIES, pytest_sessionstart


class _Options:
    collectonly = False


class _Config:
    """Just enough of pytest's config object for the hook under test."""

    def __init__(self, results: Path) -> None:
        self.option = _Options()
        self._results = results

    def getoption(self, name: str) -> str:
        assert name == "--alluredir", f"the hook asked for {name!r}"
        return str(self._results)


class _Session:
    def __init__(self, config: _Config) -> None:
        self.config = config


def _start_a_session(results: Path) -> None:
    pytest_sessionstart(_Session(_Config(results)))  # type: ignore[arg-type]


def test_the_failure_categories_reach_the_results_directory(tmp_path: Path) -> None:
    _start_a_session(tmp_path)
    copied = json.loads((tmp_path / "categories.json").read_text(encoding="utf-8"))
    assert copied == json.loads(CATEGORIES.read_text(encoding="utf-8"))


def test_the_environment_reaches_the_results_directory(tmp_path: Path) -> None:
    _start_a_session(tmp_path)
    written = (tmp_path / "environment.properties").read_text(encoding="utf-8")
    assert "BASE_URL=" in written and "Python=" in written


def test_every_category_says_which_statuses_it_groups() -> None:
    """An entry with no matched status silently groups nothing."""
    categories = json.loads(CATEGORIES.read_text(encoding="utf-8"))
    assert categories, f"{CATEGORIES} holds no categories at all"
    for category in categories:
        assert category.get("name"), f"a category in {CATEGORIES} has no name"
        assert category.get("matchedStatuses"), (
            f"category {category.get('name')!r} matches no status, so nothing "
            f"will ever land in it"
        )
