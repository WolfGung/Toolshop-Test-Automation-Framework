"""What `scripts/build-showcase.sh` leaves behind, and where the trend comes from.

The script assembles `site/` and stops there. CI hands that directory to GitHub
Pages as an artifact of the run, so a build writes no branch and pushes
nothing: that is what keeps the repository's published history from ever being
rewritten. The report's trend needs the previous publication's history, and
the build reads it back from the live site.

Every test runs the real script, against stand-ins: a local HTTP server for the
live site, a recording executable for Allure, and a scratch copy of the files
the script reads for the checkout. No test reaches the internet, and none
touches this checkout's own `site/`.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-showcase.sh"

#: The files the published report keeps its history in.
HISTORY = ("history", "history-trend", "duration-trend", "categories-trend", "retry-trend")

#: Executables put first on the script's PATH.
#: - `allure` writes down which history files were in place when it ran, the
#:   moment that decides whether the report has a trend, and leaves a report
#:   page wherever `-o` sends it, as the real one does.
#: - `git` writes down every call, refuses to push and hands the rest to git.
#: - `npx` fails: reaching it means the build went to fetch Allure from the
#:   network instead of running the one in ALLURE_BIN.
#: - `python` is the interpreter running these tests.
STAND_INS = {
    "allure": """#!/bin/sh
set -eu
here=$(dirname "$0")
ls "$2/history" > "$here/allure-saw-history" 2>/dev/null || : > "$here/allure-saw-history"
out=""
previous=""
for arg in "$@"; do
  if [ "$previous" = "-o" ]; then out="$arg"; fi
  previous="$arg"
done
mkdir -p "$out"
echo '<!doctype html><title>report</title>' > "$out/index.html"
""",
    "git": """#!/bin/sh
printf '%s\\n' "$*" >> "$(dirname "$0")/git-calls"
for arg in "$@"; do
  if [ "$arg" = push ]; then
    echo "git push is not allowed here" >&2
    exit 1
  fi
done
exec @GIT@ "$@"
""",
    "npx": """#!/bin/sh
echo "npx is not allowed here: the build has to run the allure in ALLURE_BIN" >&2
exit 1
""",
    "python": """#!/bin/sh
exec @PYTHON@ "$@"
""",
}


# ------------------------------------------------------------------ plumbing

def _nothing_listening() -> str:
    """A loopback address nothing listens on, so a connection is refused at once."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        host, port = probe.getsockname()
    return f"{host}:{port}"


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """What the script reads, copied out of this checkout, and one run's results."""
    work = tmp_path / "work"
    (work / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, work / "scripts" / SCRIPT.name)
    shutil.copytree(
        ROOT / "showcase", work / "showcase", ignore=shutil.ignore_patterns("__pycache__")
    )
    results = work / "allure-results"
    results.mkdir()
    (results / "a-result.json").write_text(
        json.dumps({
            "name": "a",
            "fullName": "tests.api.test_products_api#a",
            "status": "passed",
            "stop": 1_758_400_000_000,
            "labels": [
                {"name": "package", "value": "tests.api.test_products_api"},
                {"name": "tag", "value": "api"},
            ],
        }),
        encoding="utf-8",
    )
    return work


@pytest.fixture
def tools(tmp_path: Path) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    real = {
        # Without a git on the machine the stand-in must not call itself.
        "@GIT@": shlex.quote(shutil.which("git") or "false"),
        "@PYTHON@": shlex.quote(sys.executable),
    }
    for name, body in STAND_INS.items():
        for marker, value in real.items():
            body = body.replace(marker, value)
        path = tools / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return tools


@dataclass
class Published:
    """The live site as far as the build can tell: a directory served over HTTP."""

    root: Path
    url: str

    def put(self, name: str, body: str) -> None:
        (self.root / "report" / "history" / f"{name}.json").write_text(body, encoding="utf-8")


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def published(tmp_path: Path) -> Iterator[Published]:
    root = tmp_path / "published"
    (root / "report" / "history").mkdir(parents=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Published(root, f"http://127.0.0.1:{server.server_address[1]}/")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _build(work: Path, tools: Path, site_url: str) -> subprocess.CompletedProcess[str]:
    """Run the script the way CI does, with no way off this machine.

    Every proxy variable points at a port nothing listens on and only the
    loopback is exempt, so a request for anything but the local stand-in site
    fails at once instead of reaching the internet.
    """
    nowhere = f"http://{_nothing_listening()}"
    env = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}",
        "SITE_URL": site_url,
        "ALLURE_BIN": str(tools / "allure"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "no_proxy": "127.0.0.1",
        "NO_PROXY": "127.0.0.1",
    }
    for proxy in ("http_proxy", "https_proxy", "all_proxy"):
        env[proxy] = env[proxy.upper()] = nowhere
    return subprocess.run(
        ["bash", "scripts/build-showcase.sh", "allure-results", "videos"],
        cwd=work, env=env, capture_output=True, text=True, timeout=120,
    )


def _said(build: subprocess.CompletedProcess[str]) -> str:
    """Everything the build printed, for a failure message."""
    return f"exit {build.returncode}\n--- stdout\n{build.stdout}--- stderr\n{build.stderr}"


def _history(work: Path) -> dict[str, str]:
    """The history files the report is generated with, name to contents."""
    history = work / "allure-results" / "history"
    if not history.is_dir():
        return {}
    return {path.name: path.read_text(encoding="utf-8") for path in history.iterdir()}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


def _git_state(repo: Path) -> dict[str, list[str]]:
    """What a build could leave in a repository: its refs, the branch HEAD
    names, its registered worktrees, and every commit object in it, reachable
    or not, so a branch made and deleted again still shows."""
    objects = _git(
        repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)"
    )
    return {
        "refs": _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines(),
        "HEAD": _git(repo, "symbolic-ref", "HEAD").splitlines(),
        "worktrees": _git(repo, "worktree", "list", "--porcelain").splitlines(),
        "commits": sorted(line for line in objects.splitlines() if line.startswith("commit ")),
    }


# ------------------------------------------------------ publishing is not here

def test_the_build_leaves_no_branch_worktree_or_commit_and_never_pushes(
    work: Path, tools: Path, published: Published
) -> None:
    origin = work.parent / "origin.git"
    _git(work.parent, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    _git(work, "init", "--quiet", "--initial-branch=main")
    _git(work, "add", "--all")
    _git(
        work, "-c", "user.name=Checkout", "-c", "user.email=checkout@example.invalid",
        "commit", "--quiet", "--message=The checkout a build runs in",
    )
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "--quiet", "origin", "main")
    before = {"checkout": _git_state(work), "origin": _git_state(origin)}

    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert {"checkout": _git_state(work), "origin": _git_state(origin)} == before
    calls = tools / "git-calls"
    pushes = [
        call for call in (calls.read_text().splitlines() if calls.exists() else [])
        if "push" in call.split()
    ]
    assert pushes == [], _said(build)


def test_the_report_is_generated_where_the_next_build_reads_its_history(
    work: Path, tools: Path, published: Published
) -> None:
    """History is read back from <SITE_URL>report/history/, and Allure writes it
    inside the report. A report generated anywhere but site/report would carry
    a history that no later build ever finds."""
    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert (work / "site" / "report" / "index.html").is_file()


# ------------------------------------------------ where the trend comes from

def test_the_published_history_is_in_place_before_the_report_is_generated(
    work: Path, tools: Path, published: Published
) -> None:
    for name in HISTORY:
        published.put(name, json.dumps({"published": name}))

    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert _history(work) == {
        "history.json": '{"published": "history"}',
        "history-trend.json": '{"published": "history-trend"}',
        "duration-trend.json": '{"published": "duration-trend"}',
        "categories-trend.json": '{"published": "categories-trend"}',
        "retry-trend.json": '{"published": "retry-trend"}',
    }
    assert set((tools / "allure-saw-history").read_text().split()) == {
        "history.json",
        "history-trend.json",
        "duration-trend.json",
        "categories-trend.json",
        "retry-trend.json",
    }


def test_a_history_file_that_is_not_json_is_left_out(
    work: Path, tools: Path, published: Published
) -> None:
    """A server can answer 200 with a page of its own where a file should be.
    Allure reads such a file without a word and starts that part of the trend
    over, so the build is the one that has to refuse it, and say so."""
    published.put("history", '{"uid": "a"}')
    published.put("history-trend", "<!doctype html><title>Site not found</title>")

    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert _history(work) == {"history.json": '{"uid": "a"}'}
    assert "history-trend.json" in build.stderr


def test_a_first_publication_builds_without_a_trend(
    work: Path, tools: Path, published: Published
) -> None:
    """The site answers, but there is nothing on it yet."""
    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert _history(work) == {}
    assert (work / "site" / "index.html").is_file()
    assert (work / "site" / "report" / "index.html").is_file()
    assert "no trend" in build.stdout


def test_an_unreachable_site_means_no_trend_and_the_build_goes_on(
    work: Path, tools: Path
) -> None:
    build = _build(work, tools, f"http://{_nothing_listening()}/")

    assert build.returncode == 0, _said(build)
    assert _history(work) == {}
    assert (work / "site" / "index.html").is_file()
    assert (work / "site" / "report" / "index.html").is_file()
    assert "no trend" in build.stdout


def test_history_an_earlier_build_left_behind_is_replaced_not_merged(
    work: Path, tools: Path, published: Published
) -> None:
    """A local rebuild finds the results directory as the last build left it.
    Anything already in its history came from an earlier download, not from
    the site as it is now, and must not reach this report."""
    left = work / "allure-results" / "history"
    left.mkdir()
    (left / "history.json").write_text('{"uid": "an earlier build"}', encoding="utf-8")
    (left / "retry-trend.json").write_text("[]", encoding="utf-8")
    published.put("history", '{"uid": "published"}')

    build = _build(work, tools, published.url)

    assert build.returncode == 0, _said(build)
    assert _history(work) == {"history.json": '{"uid": "published"}'}
