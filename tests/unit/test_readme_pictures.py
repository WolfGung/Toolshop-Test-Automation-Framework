"""Every picture the README shows is committed, readable and quick to load.

The first screen of the README is what a client reads, and two of the things
on it are photographs of runs that really happened: the Allure report and the
CI run page. Those fail quietly. A path typo renders as a broken-image icon
that nobody who committed it ever sees, because their own checkout has the
file; a screenshot re-exported at half width turns into unreadable grey text
once the page scales it; a picture grown to a few megabytes is simply not
there yet when the reader has already scrolled past.

So the pictures are pinned here: they exist, they are what they claim to be,
they are wide enough to read, and they fit in the budget. The exporter that
makes them is `scripts/make-assets.py`, and each entry below names the command
that reproduces its picture.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"

#: A Markdown image, whether or not it is wrapped in a link: ``![alt](src)``.
PICTURE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)")

#: The pictures the README shows from this repository, each with the command
#: that makes it again. Badges are not here: they are served by somebody else
#: and are regenerated on every request, so there is nothing to keep in step.
#: A picture added to the README without a line here fails the last test.
PICTURES = {
    "allure-report-screenshot.png": "python scripts/make-assets.py",
    "showcase/images/ci-run.png": "python scripts/make-assets.py --ci-run",
    "showcase/assets/architecture.svg": "hand-drawn SVG, edited in place",
}

#: Generous for a screenshot of a page: the two committed ones are well under
#: a quarter of it. Crossing this means something was exported at a scale
#: factor, or saved as a photograph of a screen rather than a screenshot.
BUDGET_BYTES = 400 * 1024

#: GitHub renders the README in a column narrower than these images, so they
#: are scaled down; below this width the text inside a screenshot stops
#: surviving that scaling.
LEAST_WIDTH_PX = 1000

PNGS = sorted(name for name in PICTURES if name.endswith(".png"))


def _png_size(path: Path) -> tuple[int, int]:
    """The pixel size out of the PNG header, without a library to read it.

    A PNG starts with an 8-byte signature and an IHDR chunk whose first two
    fields are the width and the height, big-endian. Reading them here keeps
    this check free of an image dependency the suite does not otherwise have.
    """
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", (
        f"{path.relative_to(ROOT)} is not a PNG, whatever it is named. "
        f"Export it again with {PICTURES[str(path.relative_to(ROOT))]}."
    )
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _shown() -> dict[str, str]:
    """Every picture the README shows from this repository, source to alt text."""
    text = README.read_text(encoding="utf-8")
    return {
        match.group("src"): match.group("alt")
        for match in PICTURE.finditer(text)
        if not match.group("src").startswith(("http://", "https://"))
    }


@pytest.mark.parametrize("name", sorted(PICTURES), ids=lambda v: v)
def test_a_picture_the_readme_shows_is_committed(name: str) -> None:
    assert (ROOT / name).is_file(), (
        f"README.md shows {name}, which is not in the repository — it renders "
        f"as a broken image for everyone but whoever has it locally. Make it "
        f"with `{PICTURES[name]}` and commit it."
    )


@pytest.mark.parametrize("name", PNGS, ids=lambda v: v)
def test_a_screenshot_is_a_png_wide_enough_to_read(name: str) -> None:
    width, height = _png_size(ROOT / name)
    assert width >= LEAST_WIDTH_PX, (
        f"{name} is {width}x{height}px, narrower than the {LEAST_WIDTH_PX}px "
        f"that survives being scaled into the README's column: the text in it "
        f"will not be legible. Export it again with `{PICTURES[name]}` rather "
        f"than shrinking the file."
    )


@pytest.mark.parametrize("name", sorted(PICTURES), ids=lambda v: v)
def test_a_picture_loads_with_the_page_instead_of_after_it(name: str) -> None:
    weight = (ROOT / name).stat().st_size
    assert weight <= BUDGET_BYTES, (
        f"{name} is {weight // 1024} KB, over the {BUDGET_BYTES // 1024} KB "
        f"budget for a picture on the first screen. Crop it or take it at a "
        f"smaller viewport with `{PICTURES[name]}`; compressing it further "
        f"would leave the text in it unreadable, which defeats the picture."
    )


@pytest.mark.parametrize("name", sorted(PICTURES), ids=lambda v: v)
def test_a_picture_says_what_it_shows(name: str) -> None:
    """A reader on a screen reader, or on a slow connection, gets the alt text."""
    alt = _shown().get(name)
    assert alt and len(alt.split()) >= 5, (
        f"README.md shows {name} with alt text {alt!r}. It is what a reader "
        f"gets when the image does not load, so it has to describe what is in "
        f"the picture, not name the file."
    )


def test_every_picture_in_the_readme_is_pinned_here() -> None:
    """Without this, dropping a line from PICTURES would quietly check nothing."""
    assert set(_shown()) == set(PICTURES), (
        "the pictures README.md shows are not the ones this module pins.\n"
        f"  shown:  {sorted(_shown())}\n  pinned: {sorted(PICTURES)}\n"
        "A picture added to the README needs a line in PICTURES naming the "
        "command that makes it again."
    )
