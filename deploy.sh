#!/usr/bin/env bash
# One-command Vercel deploy: assemble .deploy/ from the repo (no duplicated
# source), regenerate app.html from server.PAGE, then ship. Run from repo root.
#   bash deploy.sh            # assemble + deploy to prod
#   bash deploy.sh --dry      # assemble + verify only, no deploy
set -euo pipefail
cd "$(dirname "$0")"

rm -rf .deploy && mkdir -p .deploy/api
cp vercel-app/api/*.py .deploy/api/
cp vercel-app/vercel.json crosscheck.py samples.json demo_snapshot.json .deploy/
cp web/index.html .deploy/index.html
python -c "import server; open('.deploy/app.html','w',encoding='utf-8').write(server.PAGE)"

# sanity: the built dashboard must carry all 12 endpoints, or a mode 404s live
n=$(grep -oE "/api/[a-z-]+" .deploy/app.html | sort -u | wc -l)
[ "$n" -eq 12 ] || { echo "FAIL: app.html has $n/12 endpoints"; exit 1; }
echo "assembled .deploy/ — app.html OK ($n endpoints)"

[ "${1:-}" = "--dry" ] && { echo "dry run, not deploying"; exit 0; }

cd .deploy
# .deploy/ is rebuilt fresh each run, so re-link it to the existing project every
# time (else --yes would spin up a NEW project at the wrong URL).
vercel link --yes --project crosscheck-btl
# BTL_API_KEY already lives in the project's env from the first deploy; reused.
# first time only: vercel env add BTL_API_KEY production   (paste your scoped key)
vercel deploy --prod --yes
