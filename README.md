# Crosscheck — a reliability layer on the BTL runtime

Single LLM calls fail silently: they return a confident, wrong value and you
never know. Crosscheck sends the **same extraction prompt to two providers in
parallel through the BTL gateway**, then:

- **Agree** → auto-accept the field (high confidence, green).
- **Disagree** → a **judge** pass adjudicates and the field is **flagged for
  human review** (red). Disagreement *is* the hallucination signal.
- **One provider 5xx / times out** → the call **fails over** to the other
  provider. (The BTL gateway really does return intermittent 500s — resilience
  is a feature here, not a nice-to-have.)

This is only possible *because* it's a multi-provider gateway — the whole point
of the BTL runtime.

## BTL runtime endpoints used
- `POST /v1/chat/completions` — extraction (×2 providers) + judge, via `gpt-4o-mini` and `deepseek-chat-v3`
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
On a labeled extraction set, the benchmark reports:
- **Accuracy**: model A alone vs model B alone vs **Crosscheck final** (judge lifts it above either single model).
- **Catch rate**: % of all field errors Crosscheck flagged for review.
- **Flag precision**: % of flags that were real errors (low false-alarm).
- **Blind spot**: % of errors where *both* models made the *same* mistake — reported honestly, because cross-checking catches disagreement, not shared errors.
- **Review burden**: % of fields a human actually has to look at.

## Files
- `crosscheck.py` — core (gateway client + failover, fan-out, judge, benchmark, self-check)
- `server.py` — dashboard (stdlib http.server)
- `samples.json` — labeled extraction benchmark
