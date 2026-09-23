#!/usr/bin/env bash
# scripts/build-showcase.sh — assemble the showcase site in site/ from one run.
#
#   bash scripts/build-showcase.sh [allure-results] [videos]
#
# site/ gets the Allure report, the page showcase/build.py writes from the same
# results, the two diagrams and the checkout recording, when the run left one.
# Nothing is published from here: the CI workflow deploys site/ to GitHub Pages
# as an artifact of the run, so this script writes no branch, makes no commit
# and pushes nothing.
#
# The report's trend is carried from one publication to the next by Allure's
# history files, and those are read back from the live site at SITE_URL. A
# first publication has none and an unreachable site gives none; either way
# the report shows this run alone, and the build goes on.
#
#   SITE_URL    the published site (default: this repository's Pages address)
#   ALLURE_BIN  an allure executable to run instead of the pinned
#               allure-commandline, which is otherwise fetched through npx
set -euo pipefail

RESULTS="${1:-allure-results}"
VIDEOS="${2:-videos}"
SITE="site"
SITE_URL="${SITE_URL:-https://wolfgung.github.io/Toolshop-Test-Automation-Framework/}"
ALLURE_VERSION="2.30.0"

rm -rf "$SITE"

# The history is replaced, never merged. A results directory that an earlier
# local build already used still holds the history that build downloaded, and
# Allure would take it as this publication's own. Each file is then read on its
# own, because Allure uses each on its own: one that is missing costs only its
# part of the trend.
rm -rf "$RESULTS/history"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
carried=0
for name in history history-trend duration-trend categories-trend retry-trend; do
  url="${SITE_URL%/}/report/history/$name.json"
  if ! curl --fail --silent --show-error --location --max-time 20 \
       --output "$staging/$name.json" "$url"; then
    echo "build: could not read $name.json from $url" >&2
    continue
  fi
  # Arriving is not enough: a server can answer 200 with a page of its own
  # where the file should be. Allure 2.30 reads a history file that is not
  # JSON without a word and starts that part of the trend over, so it is
  # refused here, where the log can say so.
  if ! python -m json.tool "$staging/$name.json" >/dev/null; then
    echo "build: $name.json from $url is not valid JSON, so it is left out" >&2
    continue
  fi
  mkdir -p "$RESULTS/history"
  mv "$staging/$name.json" "$RESULTS/history/"
  carried=$((carried + 1))
done
if [ "$carried" -eq 0 ]; then
  echo "build: no Allure history came from $SITE_URL — the report shows this run with no trend"
else
  echo "build: carried $carried of 5 Allure history files over from $SITE_URL"
fi

if [ -n "${ALLURE_BIN:-}" ]; then
  allure=("$ALLURE_BIN")
else
  allure=(npx -y "allure-commandline@$ALLURE_VERSION")
fi
"${allure[@]}" generate "$RESULTS" --clean -o "$SITE/report"

python showcase/build.py \
  --results "$RESULTS" --out "$SITE" \
  --revision "${GITHUB_SHA:-local}" \
  --run-url "${RUN_URL:-}"

mkdir -p "$SITE/assets" "$SITE/media"
cp showcase/assets/*.svg "$SITE/assets/"

# Two recordings can come out of the same run: the checkout test that reaches
# payment, and the one that carries the guest all the way to a confirmed
# order. The order test is the complete flow, so it is published when present;
# the payment-step recording is only a fallback. This is a deliberate choice
# by name, not a guess by file size — both recordings are well above the
# truncated-file floor, so size cannot tell them apart. `showcase/build.py`
# picks by the same names in the same order, and `-size +10240c` is its
# MIN_VIDEO_BYTES written in the units find counts: bytes, not 1 KB blocks,
# so the two floors are the same 10 KiB rather than 10240 against 10000.
video=""
for pattern in \
  '*guest_can_place_an_order*.webm' \
  '*guest_reaches_payment_step*.webm'
do
  candidate=$(find "$VIDEOS" -name "$pattern" -size +10240c 2>/dev/null | sort | head -1 || true)
  if [ -n "$candidate" ]; then
    video="$candidate"
    break
  fi
done
if [ -n "$video" ]; then
  echo "build: using recording $video"
  cp "$video" "$SITE/media/checkout.webm"
else
  echo "build: no recording found in $VIDEOS — the page will show no video" >&2
fi

# A Pages artifact is served as it is, without Jekyll, so this marker changes
# nothing there; it keeps site/ served the same from anywhere that does run it.
touch "$SITE/.nojekyll"
