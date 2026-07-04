# Crosscheck — a reliability layer on the BTL runtime

Single LLM calls fail silently: they return a confident, wrong value and you
never know. Crosscheck sends the **same extraction prompt to two providers in
parallel through the BTL gateway**, then:

- **Agree** → auto-accept the field (high confidence, green).
- **Disagree** → a **judge** pass adjudicates and the field is **flagged for
  human review** (red). Disagreement is the confidence signal.
- **One provider 5xx / times out** → the call **fails over** to the other
  provider. (The BTL gateway really does return intermittent 500s — resilience
  is a feature here, not a nice-to-have.)

This is only possible *because* it's a multi-provider gateway — the whole point
of the BTL runtime.

## BTL runtime endpoints used
- `POST /v1/chat/completions` — extraction (×2 providers) + judge, via `gpt-4.1-mini` (OpenAI route) and `deepseek-chat-v3` (OpenRouter route) — two genuinely different providers behind one gateway
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
On a labeled extraction set (15 samples, 60 fields), the live benchmark reports:
- **Accuracy**: model A alone vs model B alone vs Crosscheck consensus. Honest
  finding: two capable 2026 models mostly agree, so on clean text Crosscheck is
  **on par (~93%) with the stronger single model — it does not boost raw accuracy**.
- **Flag precision**: **100%** — every field Crosscheck flagged was a genuine
  cross-provider discrepancy (zero false alarms).
- **Review burden**: **~3%** — the fraction of fields a human actually looks at.
- **Blind spot**: % of errors where *both* providers made the *same* choice —
  cross-checking is blind to shared bias. Reported, not hidden. (Verified: adding
  a third provider did not fix these, because they are shared, defensible readings.)

The honest value is a **calibrated confidence signal + cross-provider failover**,
not higher accuracy. On noisier, more ambiguous inputs (where providers genuinely
diverge) the flag catches more real errors.

## Files
- `crosscheck.py` — core (gateway client + failover, fan-out, judge, benchmark, self-check)
- `server.py` — dashboard (stdlib http.server)
- `samples.json` — labeled extraction benchmark
