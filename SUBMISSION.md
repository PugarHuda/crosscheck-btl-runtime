# Submission kit — Crosscheck

Everything to fill the form and record the 2-minute video. English (demo day is global).

---

## 1. Submission form fields

**Project name:** Crosscheck

**One-line:** A reliability layer on the BTL runtime — same prompt to two providers, agree = auto-accept, disagree = flag, one provider down = fail over.

**Short description (paste this):**
> LLM extraction fails silently: one model returns a confident wrong value and you never know. Crosscheck sends the same extraction prompt to two providers in parallel through the BTL gateway. Fields where both providers agree are auto-accepted; fields where they disagree are adjudicated by a judge pass and flagged for human review — disagreement is the hallucination signal. If a provider returns a 5xx or times out (which the gateway does intermittently), the call automatically fails over to the other provider, so cross-checking degrades gracefully instead of crashing. On a labeled extraction benchmark it lifts field accuracy above either single model and flags the majority of the remaining errors for review, with the shared-error blind spot reported honestly rather than hidden. This is only possible because the BTL runtime is a multi-provider gateway — that is the entire point of the project.

**Which BTL runtime endpoint(s) you used:**
> POST /v1/chat/completions — extraction across two providers (gpt-4o-mini + deepseek-chat-v3) plus the judge pass. GET /v1/models — to confirm available model ids. Multi-provider fan-out and cross-provider failover are the core of the project.

**Repo:** <your GitHub link>
**Team name / members:** <fill in>

---

## 2. Two-minute video script (shot by shot)

Total ~115s. Record at 1080p, browser zoomed so text is readable. Speak calmly.

**[0:00–0:12] Hook — the problem** *(screen: dashboard homepage)*
> "A single LLM call fails silently. It hands you a confident, wrong value and you have no idea. If you're extracting data, that error just flows straight into your database."

**[0:12–0:25] The idea** *(screen: point at the subtitle line)*
> "Crosscheck sits on top of the BTL runtime. Because BTL is a multi-provider gateway, I send the exact same prompt to two providers at once — and let them check each other."

**[0:25–0:55] Live extraction** *(pick the Acme invoice sample → Run Crosscheck)*
> "Here's a messy invoice. Both providers run in parallel."
*(cards appear)*
> "Green fields — both providers agreed, auto-accepted. This red one — they disagreed on the total, so a judge pass adjudicated it and flagged it for a human. Disagreement is the hallucination signal. You review the one risky field instead of trusting all of them blindly."

**[0:55–1:15] Failover** *(if a 500 happens naturally, point at the banner; otherwise say this over a normal run)*
> "The gateway sometimes returns a 500. Instead of crashing, Crosscheck fails over to the other provider automatically — you see the failover banner here. Resilience is built in, which matters on real infrastructure."

**[1:15–1:45] The numbers** *(Run Benchmark → stats appear)*
> "On a labeled extraction set: model A alone, model B alone — and Crosscheck, which lands higher than either, because the judge resolves the disagreements. It flags this percentage of all errors for review, with high precision. And I report the blind spot honestly — cases where both models made the same mistake, which cross-checking can't catch."

**[1:45–1:55] Close** *(screen: back to homepage)*
> "Crosscheck — turning two providers on one gateway into a reliability guarantee. Built entirely on the BTL runtime. Thanks."

---

## 3. Pre-record checklist
- [ ] `python crosscheck.py` → prints "self-check OK"
- [ ] `$env:BTL_API_KEY` set; `python crosscheck.py models` → confirm ids; fix `BTL_MODEL_B` if `deepseek-chat-v3` is wrong
- [ ] `python crosscheck.py bench` once → confirm `acc_final` ≥ `acc_a` and `acc_b` (if not, ping me to tune the judge prompt) — note the real numbers so you can re-say them if the live run stalls
- [ ] `python server.py`, browser at localhost:8000, zoom to ~125%
- [ ] Do one full dry run of the script end to end before recording
- [ ] Repo pushed, key NOT committed (it only lives in the env var — good)
