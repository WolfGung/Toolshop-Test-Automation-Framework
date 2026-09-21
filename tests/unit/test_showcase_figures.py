"""Every count the project states about itself is a count pytest collects.

That covers the two diagrams on the page, the profile cover, and the README's
coverage table — three places quoting the same numbers where nobody would
notice them going stale. The cover is worst: it is an exported image, so a
client sees the number long after the suite moved on. The README is read most.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "showcase" / "assets"
SVG = "{http://www.w3.org/2000/svg}"
FIGURES = ("architecture.svg", "ci-pipeline.svg")
COVER = "cover.html"
README = "README.md"
SOURCES = (*FIGURES, COVER, README)

#: "11 cases", and "1 case" if a figure ever has to say it.
DRAWN_COUNT = re.compile(r"^(\d+) cases?$")

#: A count the cover states with the words that qualify it: "32 tests passed".
#: A card's number stands alone, so the words are empty and the card's layer
#: name labels it instead.
STATED_COUNT = re.compile(r"^(\d+)\s*(.*)$")

#: What the reader of the cover pays attention to: the boxes that hold a number,
#: and the pieces inside them. `.layer` names a card, `.n` is a number, `.t` is
#: the badge's second line, which states a number of its own.
COVER_REGIONS = frozenset({"card", "passed"})
COVER_PARTS = frozenset({"layer", "n", "t"})

#: The README's opening paragraph — everything above its first "## " heading —
#: and the body of its Coverage section. Those are the two places it states a
#: count, and the only two this test reads.
README_INTRO = re.compile(r"\A(.*?)^## ", re.MULTILINE | re.DOTALL)
README_COVERAGE = re.compile(r"^## Coverage\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)

#: A row of the README's coverage table: "| API | 11 | Pagination, schema… |".
#: The second cell has to be the number and nothing else, which is what keeps
#: this off the other tables in the file — their second cell holds prose, or a
#: default written as code (`30000`).
TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE)

#: The headline in the README's opening paragraph, which is also the number the
#: showcase page leads with: "32 automated cases across API, UI and…".
HEADLINE_COUNT = re.compile(r"(\d+) automated cases")

#: HTML elements that never have an end tag, so they never go on the stack.
VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)

#: What to do when a count no longer matches, per kind of source.
FIX = {
    ".svg": (
        "The figure is hand-drawn SVG: edit the number in showcase/assets/{source}, "
        "and check the coverage table in README.md, which quotes the same counts."
    ),
    ".html": (
        "Edit the number in showcase/assets/{source} and export the cover again "
        "(python -m http.server -d site 8899 & PYTHONPATH=. python "
        "scripts/make-assets.py), because the committed PNG still shows the old "
        "one. README.md quotes the same counts."
    ),
    ".md": (
        "Edit the number in {source} — the opening paragraph states the total "
        "and the coverage table states the rest — and check showcase/assets, "
        "which draws the same counts, and the showcase page, which reads them "
        "out of the run it publishes."
    ),
}


def _path(source: str) -> str:
    """Where a source lives, for a message someone has to act on."""
    return source if source == README else f"showcase/assets/{source}"

# Every count the project states about itself, with the selection it claims to
# describe. ``-m ""`` is what the gate job runs when the architecture figure
# says "run every layer"; the nightly browser job runs ``-m "ui or e2e"``
# itself. The cover and the README count the product only: three layers, their
# total, and the smoke set drawn from them — which is why neither names a total
# for the whole run, where the framework's own checks are counted too. Adding a
# count to a source without adding it here fails the last test in this module.
CLAIMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("architecture.svg", "tests/api"): ("-m", "", "tests/api"),
    ("architecture.svg", "tests/ui"): ("-m", "", "tests/ui"),
    ("architecture.svg", "tests/e2e"): ("-m", "", "tests/e2e"),
    ("ci-pipeline.svg", "browser suite"): ("-m", "ui or e2e"),
    ("cover.html", "API"): ("-m", "", "tests/api"),
    ("cover.html", "UI"): ("-m", "", "tests/ui"),
    ("cover.html", "End-to-end"): ("-m", "", "tests/e2e"),
    ("cover.html", "N tests passed"): ("-m", "", "tests/api", "tests/ui", "tests/e2e"),
    ("cover.html", "N of them in the smoke set"): ("-m", "smoke"),
    ("README.md", "N automated cases"): ("-m", "", "tests/api", "tests/ui", "tests/e2e"),
    ("README.md", "API"): ("-m", "", "tests/api"),
    ("README.md", "UI"): ("-m", "", "tests/ui"),
    ("README.md", "E2E"): ("-m", "", "tests/e2e"),
    ("README.md", "Smoke (of the cases above)"): ("-m", "smoke"),
}


class _CoverReader(HTMLParser):
    """The numbers cover.html states, grouped by the box each sits in.

    Walks the page once, tracking which COVER_REGIONS container (a `.card` or
    the `.passed` badge) each tag is nested inside. Within a container, the
    text of any COVER_PARTS span is captured: `.layer` names a card, `.n` is
    the number itself, `.t` is the badge's second line, which states a number
    of its own. VOID tags never get a matching end tag, so they are never
    pushed onto the nesting stack — pushing one would leave the stack one
    entry too deep for the rest of the document.
    """

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[dict[str, str] | None] = [None]
        self.regions: list[dict[str, str]] = []
        self._capture: tuple[dict[str, str], str] | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        region = self._stack[-1]
        if classes & COVER_REGIONS:
            region = {}
            self.regions.append(region)
        if tag not in VOID:
            self._stack.append(region)
        part = classes & COVER_PARTS
        if part and region is not None:
            self._capture = (region, next(iter(part)))
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture is not None:
            region, part = self._capture
            region[part] = "".join(self._buffer).strip()
            self._capture = None
        if tag not in VOID and len(self._stack) > 1:
            self._stack.pop()


@lru_cache(maxsize=None)
def _drawn_cover() -> dict[str, int]:
    """Every count cover.html states, keyed by the words that describe it.

    A card is titled by its `.layer` span and holds one number, in `.count
    .n`. The badge below the cards has no title of its own — its two lines
    each state a number followed by the words that qualify it ("32 tests
    passed", "10 of them in the smoke set") — so those words become the
    title, with the number itself replaced by "N".
    """
    reader = _CoverReader()
    reader.feed((ASSETS / COVER).read_text())
    drawn: dict[str, int] = {}
    for region in reader.regions:
        if "layer" in region:
            match = STATED_COUNT.match(region["n"])
            assert match, f"{COVER}: {region['layer']!r} card holds {region['n']!r}, not a number"
            drawn[region["layer"]] = int(match.group(1))
        else:
            for part in ("n", "t"):
                text = region[part]
                match = STATED_COUNT.match(text)
                assert match, f"{COVER}: the badge's {part!r} line holds {text!r}, not a number"
                count, words = match.groups()
                title = f"N {words}" if words else "N"
                drawn[title] = int(count)
    return drawn


@lru_cache(maxsize=None)
def _drawn_readme() -> dict[str, int]:
    """Every count the README states, keyed by the words that introduce it.

    Two places state one, and only those two are read: the opening paragraph,
    which gives the total the showcase page also leads with, and the rows of
    the coverage table. Reading the whole file instead would pick up every
    other number in it — an HTTP status, a default timeout, a viewport — and
    the test below that insists every count found is checked would start
    failing on prose.
    """
    text = (ROOT / README).read_text()
    intro = README_INTRO.search(text)
    coverage = README_COVERAGE.search(text)
    assert intro and coverage, (
        f"{README} no longer has an opening paragraph above its first heading "
        f"and a '## Coverage' section, which are the two places this test "
        f"reads. Restore them, or move this reader to wherever the counts went."
    )

    headline = HEADLINE_COUNT.search(intro.group(1))
    assert headline, (
        f"{README}'s opening paragraph no longer states a count matching "
        f"{HEADLINE_COUNT.pattern!r}. It is the number the showcase page leads "
        f"with; if the wording changed, change this pattern with it."
    )
    rows = TABLE_ROW.findall(coverage.group(1))
    assert rows, (
        f"{README}'s Coverage section has no table row of the shape "
        f"'| <layer> | <count> |'. Without one this test would pass by "
        f"finding nothing."
    )

    drawn = {"N automated cases": int(headline.group(1))}
    for label, count in rows:
        drawn[label] = int(count)
    return drawn


def _drawn_source(source: str) -> dict[str, int]:
    """Every count `source` states, dispatched by how each kind is written."""
    if source == COVER:
        return _drawn_cover()
    if source == README:
        return _drawn_readme()
    return _drawn(source)


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


@pytest.mark.parametrize(("source", "box"), list(CLAIMS), ids=lambda v: v)
def test_a_source_states_the_number_of_cases_pytest_collects(source: str, box: str) -> None:
    selection = CLAIMS[(source, box)]
    drawn = _drawn_source(source).get(box)
    assert drawn is not None, (
        f"{_path(source)} no longer states a count under \"{box}\". Either it "
        f"was renamed, in which case fix CLAIMS in this file, or the count was "
        f"dropped."
    )
    collected = _collected(selection)
    assert drawn == collected, (
        f'{_path(source)} states {drawn} for "{box}", but pytest collects '
        f"{collected}: `pytest {shlex.join(selection)}`.\n"
        f"A test was added, removed or re-marked. "
        + FIX[Path(source).suffix].format(source=source)
    )


def test_every_case_count_the_project_states_is_checked() -> None:
    """Without this, a loose reading of the files would pass by finding nothing."""
    drawn = {(source, box) for source in SOURCES for box in _drawn_source(source)}
    assert drawn == set(CLAIMS), (
        "the case counts found in the showcase sources and the README do not "
        f"match the ones this test checks.\n  found:   {sorted(drawn)}\n"
        f"  checked: {sorted(CLAIMS)}\n"
        "A count added to a source needs a line in CLAIMS naming the pytest "
        "selection it describes; if nothing was found at all, the sources or the "
        "way this test reads them have changed."
    )
