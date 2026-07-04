# Submission kit — Crosscheck

Everything to fill the form and record the 2-minute video. English (demo day is global).

---

## 1. Submission form fields

**Project name:** Crosscheck

**One-line:** A reliability layer on the BTL runtime — same prompt to two providers, agree = auto-accept, disagree = flag, one provider down = fail over.

**Short description (paste this):**
> LLM extraction fails silently: a model returns a confident wrong value and you never know. Crosscheck sends the same extraction prompt to two providers in parallel through the BTL gateway. Fields where they agree are auto-accepted; fields where they disagree are resolved by a strong judge model and flagged for review. The default setup pairs a cheap 4B model (gemma-3-4b-it) against a strong reference (gpt-4.1-mini): on a 23-sample benchmark it lifts the cheap model from 89.7% to 92.6% field accuracy — approaching the strong model's 94.1% — while escalating only ~10% of fields to the strong model. So you run the cheap model on the easy majority and only pay for the strong model where it actually disagrees. Every flag is a genuine discrepancy (100% precision), and if a provider 5xx's, drops the connection, or times out (we hit a live connection drop during testing), the call fails over to the other provider. When both models share the same bias, cross-checking is blind — reported honestly, not hidden. All of this works only because the BTL runtime is a multi-provider gateway.

**Which BTL runtime endpoint(s) you used:**
> POST /v1/chat/completions — extraction across two providers (gpt-4.1-mini on the OpenAI route + gemma-3-4b-it on the OpenRouter route) plus the strong judge pass. GET /v1/models — to confirm available model ids. Multi-provider fan-out, cheap/strong routing, and cross-provider failover are the core of the project.

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
> "The cheap model alone scores about ninety percent on this set. Crosscheck lifts it to ninety-two point six — close to the strong model's ninety-four — but it only escalates about ten percent of fields to the strong model. So you get near-strong accuracy while paying for the cheap model on the easy majority. Every flag is a real discrepancy — a hundred percent precision. And I report the blind spot honestly: when both models make the same mistake, cross-checking can't see it."

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
