"""The case counts drawn on the diagrams are the counts pytest collects."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "showcase" / "assets"
SVG = "{http://www.w3.org/2000/svg}"
FIGURES = ("architecture.svg", "ci-pipeline.svg")

#: "11 cases", and "1 case" if a figure ever has to say it.
DRAWN_COUNT = re.compile(r"^(\d+) cases?$")

# Every case count drawn on a figure, with the selection it claims to describe.
# ``-m ""`` is what the gate job runs when the architecture figure says "run
# every layer"; the nightly browser job runs ``-m "ui or e2e"`` itself. Adding a
# count to a figure without adding it here fails the last test in this module.
CLAIMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("architecture.svg", "tests/api"): ("-m", "", "tests/api"),
    ("architecture.svg", "tests/ui"): ("-m", "", "tests/ui"),
    ("architecture.svg", "tests/e2e"): ("-m", "", "tests/e2e"),
    ("ci-pipeline.svg", "browser suite"): ("-m", "ui or e2e"),
}


@lru_cache(maxsize=None)
def _drawn(figure: str) -> dict[str, int]:
    """Every case count in a figure, keyed by the title of the box holding it.

    Both the boxes and the text are in the file with their coordinates, so the
    pairing is read out of the drawing itself rather than out of a table kept
    beside it: a text belongs to the box it sits inside, and a box's title is
    its topmost line.
    """
    tree = ET.parse(ASSETS / figure)
    boxes = [
        (float(r.get("x")), float(r.get("y")), float(r.get("width")), float(r.get("height")))
        for r in tree.iter(f"{SVG}rect")
        if "box" in (r.get("class") or "")
    ]
    lines: dict[tuple[float, float, float, float], list[tuple[float, str]]] = {}
    for text in tree.iter(f"{SVG}text"):
        x, y = float(text.get("x")), float(text.get("y"))
        for box in boxes:
            left, top, width, height = box
            if left <= x <= left + width and top <= y <= top + height:
                lines.setdefault(box, []).append((y, (text.text or "").strip()))
                break

    drawn: dict[str, int] = {}
    for box, contents in lines.items():
        contents.sort()
        bodies = [body for _, body in contents]
        counts = [int(m.group(1)) for m in map(DRAWN_COUNT.match, bodies) if m]
        if not counts:
            continue
        assert len(counts) == 1, f"{figure}: two case counts in one box: {bodies}"
        drawn[bodies[0]] = counts[0]
    return drawn


@lru_cache(maxsize=None)
def _collected(selection: tuple[str, ...]) -> int:
    """How many tests pytest collects for one selection, counted from node ids.

    Collection runs in a subprocess because ``pytest.ini`` points every run at
    ``allure-results`` and cleans that directory on start: collecting in-process
    would delete the results of the run the page is built from. It costs about
    a third of a second and is cached per selection.
    """
    with tempfile.TemporaryDirectory() as spool:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", f"--alluredir={spool}", *selection,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"},
        )
    ids = [
        line for line in proc.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    assert ids, (
        f"pytest {shlex.join(selection)} collected nothing, so this test cannot "
        f"check anything.\n{proc.stdout}\n{proc.stderr}"
    )
    return len(ids)


@pytest.mark.parametrize(("figure", "box"), list(CLAIMS), ids=lambda v: v)
def test_a_figure_draws_the_number_of_cases_pytest_collects(figure: str, box: str) -> None:
    selection = CLAIMS[(figure, box)]
    drawn = _drawn(figure).get(box)
    assert drawn is not None, (
        f"showcase/assets/{figure} no longer draws a case count in a box titled "
        f'"{box}". Either the box was renamed, in which case fix CLAIMS in this '
        f"file, or the count was dropped from the figure."
    )
    collected = _collected(selection)
    assert drawn == collected, (
        f'showcase/assets/{figure} draws "{drawn} cases" in the "{box}" box, but '
        f"pytest collects {collected}: `pytest {shlex.join(selection)}`.\n"
        f"A test was added, removed or re-marked. The figure is hand-drawn SVG: "
        f"edit the number in showcase/assets/{figure}, and check the coverage "
        f"table in README.md, which quotes the same counts."
    )


def test_every_case_count_on_the_figures_is_checked() -> None:
    """Without this, a loose reading of the files would pass by finding nothing."""
    drawn = {(figure, box) for figure in FIGURES for box in _drawn(figure)}
    assert drawn == set(CLAIMS), (
        "the case counts found in showcase/assets do not match the ones this "
        f"test checks.\n  found:   {sorted(drawn)}\n  checked: {sorted(CLAIMS)}\n"
        "A count added to a figure needs a line in CLAIMS naming the pytest "
        "selection it describes; if nothing was found at all, the figures or the "
        "way this test reads them have changed."
    )
