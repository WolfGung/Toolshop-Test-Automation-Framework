#!/usr/bin/env bash
# scripts/publish-showcase.sh — assemble the site and push it to gh-pages.
#
# History is carried over from the previous publication: without it the report
# shows a single run and no trend.
set -euo pipefail

RESULTS="${1:-allure-results}"
VIDEOS="${2:-videos}"
SITE="site"
ALLURE_VERSION="2.30.0"

# A prior run that died mid-way (a killed job, a crashed shell) can leave a
# worktree registered without a directory, or a directory without the
# registration; either half-state must not stop this run from starting clean.
rm -rf "$SITE" published publish-tree
git worktree prune
git fetch origin gh-pages --depth 1 || true
if git rev-parse --verify origin/gh-pages >/dev/null 2>&1; then
  git worktree add published origin/gh-pages
  if [ -d published/report/history ]; then
    echo "publish: carrying over Allure history"
    cp -r published/report/history "$RESULTS/history"
  fi
fi

npx -y "allure-commandline@$ALLURE_VERSION" generate "$RESULTS" --clean -o "$SITE/report"

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
# truncated-file floor, so size cannot tell them apart.
video=""
for pattern in \
  '*guest_can_place_an_order*.webm' \
  '*guest_reaches_payment_step*.webm'
do
  candidate=$(find "$VIDEOS" -name "$pattern" -size +10k 2>/dev/null | sort | head -1 || true)
  if [ -n "$candidate" ]; then
    video="$candidate"
    break
  fi
done
if [ -n "$video" ]; then
  echo "publish: using recording $video"
  cp "$video" "$SITE/media/checkout.webm"
else
  echo "publish: no recording found in $VIDEOS — the page will show no video" >&2
fi

rm -rf published
git worktree add --detach publish-tree
cd publish-tree
git checkout --orphan gh-pages-new
git rm -rf . >/dev/null 2>&1 || true
cp -r "../$SITE/." .
touch .nojekyll
git add -A
git -c user.name="github-actions[bot]" \
    -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -m "Publish showcase for ${GITHUB_SHA:-local}"
git push --force origin gh-pages-new:gh-pages
cd ..
git worktree remove --force publish-tree
