"""Build the showcase page from the artefacts of a single run.

Every number on the page comes from the Allure results of the run being
published. Nothing here is written by hand, because a page that disagrees with
its own report is worse than no page.

Two artefacts are optional: the checkout recording and the two diagrams. They
are produced by other steps and may simply not be there. When one is missing
the page says so in words, rather than offering a broken image or a black
video frame -- a showcase that shows a broken box has already lost the reader.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

LAYERS = ("api", "ui", "e2e")

#: A recording shorter than this is a truncated file, not a video. The publish
#: step applies the same floor when it picks a file to publish.
MIN_VIDEO_BYTES = 10_000

ASSETS_DIR = Path(__file__).parent / "assets"


@dataclass
class Tally:
    """What happened to one group of results."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    unknown: int = 0
    smoke: int = 0

    @property
    def not_passed(self) -> int:
        """Everything that did not come back green, however it got there."""
        return self.total - self.passed

    def record(self, status: str, smoke: bool, where: str) -> None:
        self.total += 1
        if smoke:
            self.smoke += 1
        if status == "passed":
            self.passed += 1
        elif status in {"failed", "broken"}:
            self.failed += 1
        elif status == "skipped":
            self.skipped += 1
        elif status == "unknown":
            self.unknown += 1
        else:
            # Every counted result has to land in a bucket the page can show.
            # Silently dropping one produces a page whose own totals do not add
            # up, which is the single thing this page cannot afford.
            raise ValueError(f"unrecognised Allure status {status!r} in {where}")


@dataclass
class RunSummary:
    """One run, split by what each result is actually evidence of.

    The application and the suite's own tooling are counted apart, because the
    page leads with the first. A reader looking at a project about testing a
    storefront reads the big number as coverage of that storefront, and tests of
    this builder would inflate it on work that is not product coverage at all.
    """

    product: Tally = field(default_factory=Tally)
    framework: Tally = field(default_factory=Tally)
    by_layer: dict[str, int] = field(default_factory=dict)
    finished: datetime = datetime.fromtimestamp(0, tz=timezone.utc)

    # The whole run, for anything that needs it. Derived, so the parts and the
    # whole cannot drift apart.
    @property
    def total(self) -> int:
        return self.product.total + self.framework.total

    @property
    def passed(self) -> int:
        return self.product.passed + self.framework.passed

    @property
    def failed(self) -> int:
        return self.product.failed + self.framework.failed

    @property
    def skipped(self) -> int:
        return self.product.skipped + self.framework.skipped

    @property
    def unknown(self) -> int:
        return self.product.unknown + self.framework.unknown

    @property
    def smoke(self) -> int:
        return self.product.smoke + self.framework.smoke


def summarise(results_dir: Path) -> RunSummary:
    files = sorted(Path(results_dir).glob("*-result.json"))
    if not files:
        raise ValueError(f"no Allure results in {results_dir}")

    summary = RunSummary(by_layer={layer: 0 for layer in LAYERS})
    stops: list[int] = []
    for path in files:
        body = json.loads(path.read_text(encoding="utf-8"))
        tags = {l["value"] for l in body.get("labels", []) if l.get("name") == "tag"}

        layers = [layer for layer in LAYERS if layer in tags]
        if len(layers) > 1:
            # A case proves its thing at one layer; two markers means the
            # selection rules in pytest.ini no longer mean what the page says
            # they mean. Counting it once under whichever tag sorts first would
            # hide that, and the layer totals would quietly stop adding up.
            raise ValueError(
                f"{body.get('name', path.name)} carries more than one layer "
                f"tag ({', '.join(layers)}); a case belongs to one layer"
            )
        for layer in layers:
            summary.by_layer[layer] += 1

        group = summary.product if layers else summary.framework
        group.record(
            body.get("status", "unknown"), "smoke" in tags, where=path.name
        )

        if body.get("stop"):
            stops.append(int(body["stop"]))

    if stops:
        summary.finished = datetime.fromtimestamp(max(stops) / 1000, tz=timezone.utc)
    return summary


def _text(value: object) -> str:
    """Escape a value for text or for an attribute's contents."""
    return html.escape(str(value), quote=True)


def _safe_url(url: str) -> str:
    """An escaped http(s) or relative URL; empty for anything else.

    The run URL arrives from the environment, and the page puts it in an
    ``href``. Escaping alone would still let ``javascript:`` through, so the
    scheme is checked as well and an unusable value is treated as no value:
    the block that links the run is dropped rather than rendered broken.
    """
    candidate = url.strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return ""
    if candidate.startswith("//"):  # protocol-relative: not ours to resolve
        return ""
    return html.escape(candidate, quote=True)


def _pick_video(video_dir: Path) -> Path | None:
    """The newest usable recording, chosen the way the publish step chooses."""
    usable = sorted(
        p for p in Path(video_dir).glob("*.webm")
        if p.is_file() and p.stat().st_size > MIN_VIDEO_BYTES
    )
    return usable[-1] if usable else None


def _place(source: Path | None, target: Path) -> bool:
    """Put an optional artefact beside the page. True when the page can use it.

    A file already sitting at the target counts: the publish step may have put
    it there before calling this module.
    """
    if target.is_file() and target.stat().st_size > 0:
        return True
    if source is None or not Path(source).is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _resolve(page: str, name: str, keep: bool) -> str:
    """Keep or drop one conditional block of the template.

    Blocks are written as ``<!--[if name]-->...<!--[else name]-->...<!--[end
    name]-->``; the ``else`` half is optional.
    """
    pattern = re.compile(
        rf"<!--\[if {name}\]-->(?P<then>.*?)"
        rf"(?:<!--\[else {name}\]-->(?P<otherwise>.*?))?"
        rf"<!--\[end {name}\]-->",
        re.DOTALL,
    )

    def _swap(match: re.Match[str]) -> str:
        chosen = match.group("then") if keep else (match.group("otherwise") or "")
        return chosen.strip("\n")

    return pattern.sub(_swap, page)


def build_site(
    results_dir: Path,
    out_dir: Path,
    revision: str,
    run_url: str,
    video_dir: Path = Path("videos"),
    assets_dir: Path = ASSETS_DIR,
) -> None:
    summary = summarise(results_dir)
    safe_run_url = _safe_url(run_url)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    present = {
        "video": _place(_pick_video(video_dir), out_dir / "media" / "checkout.webm"),
        "architecture": _place(
            Path(assets_dir) / "architecture.svg", out_dir / "assets" / "architecture.svg"
        ),
        "pipeline": _place(
            Path(assets_dir) / "ci-pipeline.svg", out_dir / "assets" / "ci-pipeline.svg"
        ),
        "run": bool(safe_run_url),
        "product_skipped": summary.product.skipped > 0,
        "product_unknown": summary.product.unknown > 0,
        "framework": summary.framework.total > 0,
        "framework_clean": summary.framework.not_passed == 0,
    }

    page = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    for name, keep in present.items():
        page = _resolve(page, name, keep)
    page = _resolve(page, "diagrams", present["architecture"] or present["pipeline"])

    # The figures the page leads with are the product suite's; the framework's
    # are named separately, below them, in the template.
    # Everything below is escaped on its way into the page. The counts cannot
    # carry markup and the revision comes from git, but a build tool for a
    # client-facing page should not hold a working injection primitive at all.
    # ``_safe_url`` has already escaped the run URL for its attribute.
    for key, value in {
        "{{TOTAL}}": _text(summary.product.total),
        "{{PASSED}}": _text(summary.product.passed),
        "{{FAILED}}": _text(summary.product.failed),
        "{{SKIPPED}}": _text(summary.product.skipped),
        "{{UNKNOWN}}": _text(summary.product.unknown),
        "{{SMOKE}}": _text(summary.product.smoke),
        "{{API}}": _text(summary.by_layer.get("api", 0)),
        "{{UI}}": _text(summary.by_layer.get("ui", 0)),
        "{{E2E}}": _text(summary.by_layer.get("e2e", 0)),
        "{{FRAMEWORK}}": _text(summary.framework.total),
        "{{FRAMEWORK_OPEN}}": _text(summary.framework.not_passed),
        "{{RUN_TOTAL}}": _text(summary.total),
        "{{FINISHED}}": _text(summary.finished.strftime("%d %B %Y, %H:%M UTC")),
        "{{REVISION}}": _text(revision[:7]),
        "{{RUN_URL}}": safe_run_url,
    }.items():
        page = page.replace(key, value)

    (out_dir / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("allure-results"))
    parser.add_argument("--out", type=Path, default=Path("site"))
    parser.add_argument("--revision", default="local")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--videos", type=Path, default=Path("videos"))
    parser.add_argument("--assets", type=Path, default=ASSETS_DIR)
    args = parser.parse_args()
    build_site(
        args.results, args.out, args.revision, args.run_url,
        video_dir=args.videos, assets_dir=args.assets,
    )
