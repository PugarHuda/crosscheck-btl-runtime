# Crosscheck — a reliability layer on the BTL runtime

[![tests](https://github.com/PugarHuda/crosscheck-btl-runtime/actions/workflows/test.yml/badge.svg)](https://github.com/PugarHuda/crosscheck-btl-runtime/actions/workflows/test.yml)
&nbsp;·&nbsp; [MIT](LICENSE) &nbsp;·&nbsp; [Live site](https://crosscheck-btl.vercel.app) &nbsp;·&nbsp; pure Python stdlib &nbsp;·&nbsp; 78 tests

**Live:** https://crosscheck-btl.vercel.app — landing page, with the interactive dashboard at **[/app](https://crosscheck-btl.vercel.app/app)** (Vercel serverless, API key as a server-side secret). Run locally with `python server.py`. Deploy notes: [`vercel-app/DEPLOY.md`](vercel-app/DEPLOY.md).

```
                 ┌─ gpt-4.1-mini  (OpenAI route) ──┐   agree     → accept (green)
   prompt ──▶ ───┤                                 ├─▶ disagree  → strong model judges → flag (red)
                 └─ gemma-3-4b-it (OpenRouter) ─────┘   5xx/429/drop → fail over to the other
```

Single LLM calls fail silently: a model returns a confident, wrong value and you
never know. Crosscheck sends the **same extraction prompt to two providers in
parallel through the BTL gateway**, then:

- **Agree** → auto-accept the field (green).
- **Disagree** → a strong **judge** model resolves it and the field is **flagged
  for review** (red). Disagreement is the confidence signal.
- **One provider 5xx / drops the connection / times out** → the call **fails
  over** to the other provider. (We hit a live connection drop during testing —
  resilience is a feature here, not a nice-to-have.)

The default demo pairs a **cheap bulk model** (`gemma-3-4b-it`) against a **strong
reference** (`gpt-4.1-mini`): both run on every field (this is a **verification
layer**, not a cost saver), and the strong model — as judge — resolves the ~10% of
fields where they disagree, catching the cheap model's silent errors. The gateway
reports the real per-run charge via its `x-btl-customer-charge` header, so you see
exactly what verification costs. Point both at same-tier providers for a peer
cross-check instead.

This is only possible *because* it's a multi-provider gateway — the whole point
of the BTL runtime.

## BTL runtime endpoints used
- `POST /v1/chat/completions` — extraction (×2 providers) + judge, via `gpt-4.1-mini` (OpenAI route) and `gemma-3-4b-it` (OpenRouter route) — two different providers behind one gateway
- `GET /v1/models` — verify ids **and power the dashboard's model picker**: cross-check any two of the gateway's models (a curated set), chosen live (the whole point of a multi-provider gateway)
- **Savings headers** — `x-btl-customer-charge` / `x-btl-saved` / `x-btl-cache-tier` read off each response to show real per-run cost and cache savings
- **Exact-cache demo** — the dashboard's "Exact cache" mode fires the same prompt twice; the second call is a cache hit (measured ~1.5–2.4× faster, `x-btl-saved` > 0) — a live proof of a BTL-flagship feature
- **Demo resilience** — the gateway is genuinely flaky (frequent 500s). `snapshot` captures real results; if a live call fails during a demo, the dashboard replays the captured real result with a clearly-labeled "↻ Replay" banner, so a live presentation can't die on a transient outage
- **Model picker + N-model consensus** — cross-check any two of those models, or add a third for a **majority vote**: per field you get `unanimous` / `majority` / `split` with every model's vote shown. The multi-provider gateway, made interactive (`/api/models`, `/api/consensus`)
- **Batch mode** — verify a whole dataset at once: paste JSONL records, get a table with flagged cells highlighted and the real per-run cost (`/api/batch`, or `cat records.jsonl | python crosscheck.py batch`)
- **Provider compare** — run the same extraction across your chosen models and see each one's answer, real latency, and real cost side by side (fastest &amp; cheapest starred) to decide which provider to use (`/api/compare`)
- **Suggest fields** — paste a document and let a model propose the fields worth extracting (snake_case), so you don't need to know the schema up front (`/api/suggest`)
- **Export** — download any result: verified JSON for a single extraction, or CSV for the batch and compare tables (completes the verify → export workflow)
- **Self-consistency** — run one model N times at a higher temperature and see how stable each field is — a confidence axis *within* a model, distinct from cross-model disagreement (`/api/consistency`)
- **Deep verify (flagship)** — combines *both* axes — cross-model consensus **and** self-consistency — into one per-field verdict: high / medium / low. It catches the dangerous case either signal alone misses: a model that's confidently consistent (100% stable) but whose peers disagree → **low** confidence (`/api/verify`)
- **Callable API** — the dashboard generates a copy-paste `curl` for `POST /api/extract`; Crosscheck isn't just a UI, it's a verified-extraction API (returns the values plus a per-field `needs_review` flag)

## Run
```bash
# 1. self-check (offline, no key needed) — proves compare + judge + failover
python crosscheck.py

# 2. set your hackathon key
#    PowerShell:  $env:BTL_API_KEY="sk-..."
#    bash:        export BTL_API_KEY=sk-...

python crosscheck.py models     # confirm exact model ids, override with BTL_MODEL_A/B if needed

# 3. dashboard
python server.py                # -> http://localhost:8000

# CLI extras
python crosscheck.py bench                              # accuracy + real cost over the labeled set
python crosscheck.py cache                              # prove the exact cache: same prompt twice, faster+cheaper 2nd call
python crosscheck.py extract "INVOICE Acme ... TOTAL $99" vendor total
cat records.jsonl | python crosscheck.py batch         # verify many records: JSONL in -> verified JSONL out (+flagged fields)
python crosscheck.py snapshot                          # capture REAL results; the dashboard replays them (labeled) if the gateway is down
```

Pure Python **standard library** — no `pip install`. Requires **Python 3.8+**.

## The numbers (run `bench`)
On a 23-sample extraction + reasoning benchmark (68 fields), pairing a cheap
`gemma-3-4b-it` against a strong `gpt-4.1-mini`:

- **Cheap model alone: 89.7%** field accuracy.
- **Crosscheck: 92.6%** — the cheap model's real errors (`3 × 12 bottles → 12`
  instead of `36`; `Net 30 from Jul 1 → Jul 1` instead of `Jul 31`; `12 − 9 seats
  → 9` instead of `3`) get flagged and fixed by the judge, approaching the strong
  model's **94.1%**.
- **Judge fired on 10.3%** — both models run on every field; the third (judge)
  call only fires on the ~1-in-10 that disagree, so adjudication overhead is small.
- **Flag precision: 100%** — every flag was a genuine discrepancy.
- **Blind spot: 22%** — errors where *both* models made the same choice;
  cross-checking is blind to shared bias. Reported, not hidden.
- **Measured cost: ~$0.004** for the whole run (53 API calls), read live from the
  gateway's `x-btl-customer-charge` header — not estimated. Verification is a
  fraction of a cent; the gateway's exact cache trims repeat traffic further.

Honest caveat: two *same-tier* strong models rarely disagree (≈93% either way, no
boost — verified with gpt-4.1-mini + deepseek-chat-v3). Cross-checking earns its
keep when the two models differ in capability, so you can run the cheap one safely.

## Tests
Pure stdlib `unittest` — no pytest, no pip.
```bash
python test_crosscheck.py            # unit + integration (gateway mocked, no key needed)
BTL_API_KEY=... python test_crosscheck.py   # also runs 4 live gateway tests
```
- **unit** — `norm`, `_parse_json`, `validate_extract`, `GatewayError.retryable`,
  failover (5xx fails over, 4xx raises), agreement / disagreement→judge / degraded,
  judge-unavailable, benchmark scoring.
- **integration** — the real HTTP server driven over a socket with the gateway
  mocked: routing, input validation (400s), JSON serialization, 404s, `/api/benchmark`.
- **live** — real gateway; a persistent 5xx *skips* (the gateway is genuinely flaky),
  so the suite verifies our integration, not the gateway's uptime.

`python crosscheck.py` and `python server.py test` also run quick embedded self-checks.

## Files
- `crosscheck.py` — core (gateway client + failover, fan-out, judge, benchmark, self-check)
- `server.py` — dashboard (stdlib http.server) + input validation
- `samples.json` — labeled extraction benchmark
- `test_crosscheck.py` — unit + integration + live test suite
