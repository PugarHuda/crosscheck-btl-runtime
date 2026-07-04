# Crosscheck — a reliability layer on the BTL runtime

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
reference** (`gpt-4.1-mini`): the cheap model handles the easy majority, and only
the fields where it diverges get escalated to the strong model. You get
near-strong accuracy at mostly-cheap cost. Point both at same-tier providers for a
peer cross-check instead.

This is only possible *because* it's a multi-provider gateway — the whole point
of the BTL runtime.

## BTL runtime endpoints used
- `POST /v1/chat/completions` — extraction (×2 providers) + judge, via `gpt-4.1-mini` (OpenAI route) and `gemma-3-4b-it` (OpenRouter route) — two different providers behind one gateway
- `GET /v1/models` — verify available model ids

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
python crosscheck.py bench                              # accuracy numbers over the labeled set
python crosscheck.py extract "INVOICE Acme ... TOTAL $99" vendor total
```

Pure Python **standard library** — no `pip install`.

## The numbers (run `bench`)
On a 23-sample extraction + reasoning benchmark (68 fields), pairing a cheap
`gemma-3-4b-it` against a strong `gpt-4.1-mini`:

- **Cheap model alone: 89.7%** field accuracy.
- **Crosscheck: 92.6%** — the cheap model's real errors (`3 × 12 bottles → 12`
  instead of `36`; `Net 30 from Jul 1 → Jul 1` instead of `Jul 31`; `12 − 9 seats
  → 9` instead of `3`) get flagged and fixed by the judge, approaching the strong
  model's **94.1%**.
- **Escalation / review burden: 10.3%** — only ~1 field in 10 ever needed the
  strong model; the cheap model handled the rest alone.
- **Flag precision: 100%** — every flag was a genuine discrepancy.
- **Blind spot: 22%** — errors where *both* models made the same choice;
  cross-checking is blind to shared bias. Reported, not hidden.

Honest caveat: two *same-tier* strong models rarely disagree (≈93% either way, no
boost — verified with gpt-4.1-mini + deepseek-chat-v3). Cross-checking earns its
keep when the two models differ in capability, so you can run the cheap one safely.

## Tests
Pure stdlib `unittest` — no pytest, no pip.
```bash
python test_crosscheck.py            # unit + integration (gateway mocked, no key needed)
BTL_API_KEY=... python test_crosscheck.py   # also runs 3 live gateway tests
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
