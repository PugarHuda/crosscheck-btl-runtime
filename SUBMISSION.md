# Submission kit — Crosscheck

Everything to fill the form and record the 2-minute video. English (demo day is global).
**Deadline: Tue Jul 7, 2026 · 15:00 UTC** (extended). You can re-edit the form with your
registered email any time before then — last saved version is judged.

---

## 1. Submission form fields (matches the kickoff email exactly)

**Team name:** Crosscheck
**Project name:** Crosscheck
**Team members:** Pugar Huda
**Repo (GitHub link):** https://github.com/PugarHuda/crosscheck-btl-runtime

**BTL Runtime routes/models used:**
> POST /v1/chat/completions — extraction across two providers (gpt-4.1-mini on the OpenAI route + gemma-3-4b-it on the OpenRouter route) plus the strong judge pass. GET /v1/models — to confirm available model ids. We also read the gateway's x-btl-customer-charge / x-btl-saved / x-btl-cache-tier response headers to show real per-run cost and cache savings. Multi-provider fan-out, cross-provider failover, and live cost visibility are the core of the project.

### Optional-but-helpful fields — fill these, they add points
**Live app link:** https://crosscheck-btl.vercel.app  *(landing page; the interactive dashboard is at /app — Vercel Python serverless, API key stored as a server-side env secret, never exposed to the browser; falls back to a labeled replay of real captured results when the gateway 500s)*
**Demo video link:** <paste after recording — script in section 2>
**Runtime proof / request ID:**
> Live gpt-4.1-mini call through the gateway — response id `chatcmpl_aae78595af5147369f9a6cb7a03b477d`, x-railway-request-id `7QGwTJoaTAWqLvVto3UVLg`, x-hikari-trace `sin1.tr00`, x-btl-customer-charge `0.000008`.
> Fresh live capture (2026-07-06, through the deployed app): `POST /api/extract` on "3 cartons, 12 bottles per carton" caught the cheap model's `12`, judge resolved to `36`, x-btl-customer-charge `$0.000219`. `POST /api/cache-demo`: same prompt twice → 883 ms cold vs 78 ms warm (11.3× faster), x-btl-saved `$0.000008`. Every cost/saved figure is read live from the gateway's own response headers.
> Reproducible: `BTL_API_KEY=... python crosscheck.py bench` (or `cache`) prints the live cost from those headers.
**Social post link:** <optional, up to 3 bonus pts — draft in section 4>

**Short description (paste this):**
> LLM extraction fails silently: a model returns a confident wrong value and you never know. Crosscheck sends the same extraction prompt to two providers in parallel through the BTL gateway. Fields where they agree are auto-accepted; fields where they disagree are resolved by a strong judge model and flagged for review. The default setup pairs a cheap 4B model (gemma-3-4b-it) against a strong reference (gpt-4.1-mini): on a 23-sample benchmark it lifts the cheap model from 89.7% to ~93% field accuracy — approaching the strong model's ~94% — by catching and fixing the cheap model's silent errors. Both models run on every field (it is a verification layer, not a cost saver); the strong model, as judge, only fires on the ~10% that disagree. Deep-verify mode combines two confidence axes — cross-model consensus and single-model self-consistency — into one high/medium/low verdict per field, catching a model that is confidently consistent but wrong. The whole run costs about $0.004, read live from the gateway's x-btl-customer-charge header — so you see exactly what verification costs. The dashboard also lets you pick any two of the gateway's models to cross-check live — or add a third for a majority vote (unanimous / majority / split per field) — verify a whole dataset in batch (paste JSONL, get a table with flagged cells), compare providers side by side on the same task (per-model answer, real latency, real cost — fastest &amp; cheapest starred), and even suggest the fields to extract from any document (paste text, get a schema). The whole point of a multi-provider gateway. Every flag is a genuine discrepancy (100% precision), and if a provider 5xx's, hits a 429, drops the connection, or times out (we hit a live connection drop during testing), the call fails over to the other provider. When both models share the same bias, cross-checking is blind — reported honestly, not hidden. All of this works only because the BTL runtime is a multi-provider gateway.



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

**[0:55–1:15] Failover** *(tick the "simulate primary-provider outage" box, then Run — the failover fires on demand)*
> "Real gateways go down. Let me prove Crosscheck handles it — I'll flip this switch to knock out the primary provider mid-run. Instead of crashing, it fails over to the other provider automatically and tells you cross-checking is degraded, so nothing silently slips through. Resilience is built in, and I can trigger it live — no waiting for a random outage."

**[1:15–1:45] The numbers** *(pick "Benchmark" in the sidebar → stats appear)*
> ⚠️ **Record this beat over the FULL 23-sample numbers, not the raw live subset.** Live on Vercel, Benchmark computes only a 6-sample subset (serverless time limit) → it shows acc_b ≈ 67%, which contradicts the script. Two ways to fix before recording: **(a)** run `BTL_API_KEY=… python crosscheck.py snapshot` once — then the live dashboard *replays* the full 89.7 → ~93 numbers with a small "↻ replay" banner; or **(b)** narrate this beat over `python crosscheck.py bench` in a terminal (full run, real numbers). Verified 2026-07-06: without a snapshot the live subset reads acc_b 66.7 / final 91.7.
>
> "The cheap model alone scores about ninety percent. Crosscheck lifts it toward the strong model — around ninety-three to ninety-four — by catching and fixing its silent errors. Both models run on every field, so this is a verification layer, not a cost trick — but the judge only fires on the ten percent that disagree. And here's the whole run's cost, read live from the gateway's own charge header: about four tenths of a cent. Every flag is a real discrepancy — a hundred percent precision — and I report the blind spot honestly: when both models make the same mistake, cross-checking can't see it."

**[optional, ~12s — high impact] Exact-cache proof** *(pick "Exact cache" in the sidebar, then the run button)*
> "One more BTL-native thing. I fire the same prompt twice. First call — cold. Second call — served from the gateway's exact cache: faster, and cheaper, with a real saved amount in the header. Cost transparency and caching, for free, from the runtime."
*(If you include this, trim the failover beat to ~8s to stay under 2:00.)*

**[1:45–1:55] Close** *(screen: back to homepage)*
> "Crosscheck — run a cheap model safely by cross-checking it against a strong one, on one multi-provider gateway. Built entirely on the BTL runtime. Thanks."

---

## 3. Pre-record checklist
- [ ] `python crosscheck.py` → prints "self-check OK"
- [ ] `$env:BTL_API_KEY` set; `python crosscheck.py models` → confirm `gemma-3-4b-it` + `gpt-4.1-mini` exist; override `BTL_MODEL_B` if needed
- [ ] `python crosscheck.py bench` once → confirm `acc_final` > `acc_b` (cheap model) — note the real numbers so you can re-say them if the live run stalls
- [ ] open https://crosscheck-btl.vercel.app/app (or `python server.py`); the dashboard is organized by mode in a left sidebar
- [ ] **When the gateway is healthy, run `python crosscheck.py snapshot`** — captures real cache + the 12→36 catch + benchmark so the dashboard can replay them (labeled) if the gateway 500s mid-demo. (Current snapshot has the catch + cache; top up the benchmark on a good window.)
- [ ] Do one full dry run of the script end to end before recording
- [ ] Repo pushed, key NOT committed (it only lives in the env var — good)

---

## 4. Social post (optional, up to 3 bonus points)

Posting publicly is optional but judges can award up to 3 points. Paste the post link
in the form's "Social post link" field. Draft below — tweak in your own voice, tag
**@Badtheorylabs**.

**Single post (X / LinkedIn) — ready to paste:**
> Built Crosscheck for the @Badtheorylabs Runtime hackathon 🔀
>
> LLMs fail silently — a cheap model returns a confident wrong value and you never know. So I run it *and* a strong model on the same prompt through BTL's multi-provider gateway. Agree → accept. Disagree → the strong model judges it and flags it.
>
> On a 68-field benchmark it caught + fixed the cheap model's silent errors ("3×12 bottles → 12" became 36), 100% flag precision, real cost read straight off the gateway's x-btl-customer-charge header (~$0.004/run). Flip one switch in the dashboard and watch it fail over live when a provider 500s.
>
> Honest part: it's a verification layer, not a cost trick — both models run. Live: crosscheck-btl.vercel.app · Code: github.com/PugarHuda/crosscheck-btl-runtime

**If you post a thread**, split into: (1) the problem + hook, (2) the 12→36 catch with a
screenshot of the dashboard/showcase, (3) the numbers + cost header, (4) repo link.
Attach a screenshot of `showcase.html` or the dashboard — visuals lift engagement.
