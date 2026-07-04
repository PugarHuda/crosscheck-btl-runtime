# Deploying the interactive dashboard to Vercel

The dashboard is live at **https://crosscheck-app.vercel.app** — Python serverless
functions with the API key stored as a Vercel env secret (never sent to the browser).

`api/*.py` are self-contained Vercel Python functions (`/api/health`, `/api/samples`,
`/api/extract`, `/api/cache-demo`, `/api/benchmark`). They import `crosscheck.py` and
read `samples.json` / `demo_snapshot.json`, which are bundled via `vercel.json`
(`includeFiles`). The dashboard UI is `server.py`'s `PAGE`, dumped to `index.html`.

## Redeploy from the repo root

```bash
# assemble the deploy dir from the repo (no duplicated source)
mkdir -p .deploy/api
cp vercel-app/api/*.py .deploy/api/
cp vercel-app/vercel.json crosscheck.py samples.json demo_snapshot.json .deploy/
python -c "import server; open('.deploy/index.html','w',encoding='utf-8').write(server.PAGE)"

cd .deploy
vercel env add BTL_API_KEY production   # first time only; paste your scoped key
vercel deploy --prod --yes
```

## Notes
- **Benchmark** is capped to a small live subset on Vercel (serverless time limit);
  the full 23-sample run is `python crosscheck.py bench` locally. The dashboard
  serves the snapshot benchmark if one was captured.
- **Resilience:** if the gateway 500s, the functions replay the captured real result
  (`demo_snapshot.json`) with a labeled banner — verified working in production.
- **Credits:** a public dashboard calls the gateway on your key. Fine for a demo with
  cheap models; add a rate-limit or rotate the key after the event.
