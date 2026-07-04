# Submission kit — Crosscheck

Everything to fill the form and record the 2-minute video. English (demo day is global).

---

## 1. Submission form fields

**Project name:** Crosscheck

**One-line:** A reliability layer on the BTL runtime — same prompt to two providers, agree = auto-accept, disagree = flag, one provider down = fail over.

**Short description (paste this):**
> LLM extraction fails silently: a model returns a confident wrong value and you never know. Crosscheck sends the same extraction prompt to two providers in parallel through the BTL gateway. Fields where they agree are auto-accepted; fields where they disagree are resolved by a strong judge model and flagged for review. The default setup pairs a cheap 4B model (gemma-3-4b-it) against a strong reference (gpt-4.1-mini): on a 23-sample benchmark it lifts the cheap model from 89.7% to ~93% field accuracy — approaching the strong model's ~94% — by catching and fixing the cheap model's silent errors. Both models run on every field (it is a verification layer, not a cost saver); the strong model, as judge, only fires on the ~10% that disagree. The whole run costs about $0.004, read live from the gateway's x-btl-customer-charge header — so you see exactly what verification costs. Every flag is a genuine discrepancy (100% precision), and if a provider 5xx's, hits a 429, drops the connection, or times out (we hit a live connection drop during testing), the call fails over to the other provider. When both models share the same bias, cross-checking is blind — reported honestly, not hidden. All of this works only because the BTL runtime is a multi-provider gateway.

**Which BTL runtime endpoint(s) you used:**
> POST /v1/chat/completions — extraction across two providers (gpt-4.1-mini on the OpenAI route + gemma-3-4b-it on the OpenRouter route) plus the strong judge pass. GET /v1/models — to confirm available model ids. We also read the gateway's x-btl-customer-charge / x-btl-saved / x-btl-cache-tier response headers to show real per-run cost. Multi-provider fan-out, cross-provider failover, and live cost visibility are the core of the project.

**Repo:** https://github.com/PugarHuda/crosscheck-btl-runtime
**Team name / members:** <fill in — e.g. "Crosscheck · Pugar Huda">


---

## 2. Two-minute video script (shot by shot)

Total ~115s. Record at 1080p, browser zoomed so text is readable. Speak calmly.

**[0:00–0:12] Hook — the problem** *(screen: dashboard homepage)*
> "A single LLM call fails silently. It hands you a confident, wrong value and you have no idea. If you're extracting data, that error just flows straight into your database."

**[0:12–0:25] The idea** *(screen: point at the subtitle line)*
> "Crosscheck sits on top of the BTL runtime. Because BTL is a multi-provider gateway, I run a cheap model for the bulk of the work and cross-check it against a strong model — same prompt, both providers at once. Where they disagree, the strong model decides."

**[0:25–0:55] Live extraction** *(paste "Order: 3 cartons, 12 bottles per carton." → field `total_bottles` → Run Crosscheck)*
> "Here's a field that needs a bit of reasoning: three cartons of twelve bottles."
*(cards appear — total_bottles is red)*
> "The cheap model answered twelve — it grabbed the wrong number. The strong model said thirty-six. They disagree, so Crosscheck flags it red and the judge resolves it to the correct answer, thirty-six. The cheap model's silent error just got caught and fixed automatically."

**[0:55–1:15] Failover** *(if a 500 happens naturally, point at the banner; otherwise say this over a normal run)*
> "The gateway sometimes returns a 500. Instead of crashing, Crosscheck fails over to the other provider automatically — you see the failover banner here. Resilience is built in, which matters on real infrastructure."

**[1:15–1:45] The numbers** *(Run Benchmark → stats appear)*
> "The cheap model alone scores about ninety percent. Crosscheck lifts it toward the strong model — around ninety-three to ninety-four — by catching and fixing its silent errors. Both models run on every field, so this is a verification layer, not a cost trick — but the judge only fires on the ten percent that disagree. And here's the whole run's cost, read live from the gateway's own charge header: about four tenths of a cent. Every flag is a real discrepancy — a hundred percent precision — and I report the blind spot honestly: when both models make the same mistake, cross-checking can't see it."

**[1:45–1:55] Close** *(screen: back to homepage)*
> "Crosscheck — run a cheap model safely by cross-checking it against a strong one, on one multi-provider gateway. Built entirely on the BTL runtime. Thanks."

---

## 3. Pre-record checklist
- [ ] `python crosscheck.py` → prints "self-check OK"
- [ ] `$env:BTL_API_KEY` set; `python crosscheck.py models` → confirm `gemma-3-4b-it` + `gpt-4.1-mini` exist; override `BTL_MODEL_B` if needed
- [ ] `python crosscheck.py bench` once → confirm `acc_final` > `acc_b` (cheap model) — note the real numbers so you can re-say them if the live run stalls
- [ ] `python server.py`, browser at localhost:8000, zoom to ~125%
- [ ] Do one full dry run of the script end to end before recording
- [ ] Repo pushed, key NOT committed (it only lives in the env var — good)
