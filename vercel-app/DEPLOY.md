# Deploying to Vercel (one site: landing + dashboard + API)

Live at **https://crosscheck-btl.vercel.app** — the landing page at `/`, the
interactive dashboard at `/app`, and Python serverless functions at `/api/*`, all in
one project. The API key is a Vercel env secret (never sent to the browser).

`api/*.py` are self-contained Vercel Python functions — one per mode: `/api/health`,
`/api/models`, `/api/samples`, `/api/extract`, `/api/verify`, `/api/batch`,
`/api/consensus`, `/api/consistency`, `/api/compare`, `/api/suggest`,
`/api/benchmark`, `/api/cache-demo`. Each is a thin wrapper over one `cc.api_*`
function (single source of truth). They import `crosscheck.py` and
read `samples.json` / `demo_snapshot.json`, bundled via `vercel.json` (`includeFiles`).
`index.html` is the landing (`web/index.html`); `app.html` is `server.py`'s `PAGE`
(the dashboard), served at `/app` via `cleanUrls`.

## Redeploy from the repo root

**Easy path:** `bash deploy.sh` (assembles `.deploy/`, regenerates `app.html`,
verifies all 12 endpoints are wired, then ships). `bash deploy.sh --dry` to
build + verify without deploying. First time only, set the key once:
`cd .deploy && vercel env add BTL_API_KEY production`. The manual equivalent:

```bash
# assemble the deploy dir from the repo (no duplicated source)
mkdir -p .deploy/api
cp vercel-app/api/*.py .deploy/api/
cp vercel-app/vercel.json crosscheck.py samples.json demo_snapshot.json .deploy/
cp web/index.html .deploy/index.html
cp web/404.html .deploy/404.html
python -c "import server; open('.deploy/app.html','w',encoding='utf-8').write(server.PAGE)"

cd .deploy
vercel env add BTL_API_KEY production   # first time only; paste your scoped key
vercel deploy --prod --yes
```

## Notes
- **Benchmark** is capped to a small live subset on Vercel (serverless time limit);
  the full 23-sample run is `python crosscheck.py bench` locally. The function serves
  the snapshot benchmark if one was captured.
- **Resilience:** if the gateway 500s, the functions replay the captured real result
  (`demo_snapshot.json`) with a labeled banner — verified working in production.
- **Security:** security headers + CSP are set in `vercel.json`. A public dashboard
  still calls the gateway on your key — fine for a demo with cheap models; add a
  rate-limit or rotate the key after the event.
