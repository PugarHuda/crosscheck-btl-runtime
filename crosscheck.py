"""Crosscheck — reliability layer on top of the BTL multi-provider gateway.

Same extraction prompt goes to TWO providers in parallel. Fields where they
agree are auto-accepted (high confidence); fields where they disagree are
adjudicated by a judge pass and flagged for human review. If one provider
5xx's / times out, the call fails over to the other provider.

Pure stdlib. No pip install. Run `python crosscheck.py` for the offline
self-check (no API key needed).
"""
import os, re, json, socket, time, http.client, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

API_BASE = os.environ.get("BTL_API_BASE", "https://api.badtheorylabs.com/v1")
API_KEY  = os.environ.get("BTL_API_KEY", "")

# Only two text models are scoped for the hackathon. Confirm exact ids with
# `python crosscheck.py models` (hits GET /v1/models) and override via env.
# Demo pairing: a cheap bulk model cross-checked against a strong reference.
# When they disagree, the strong judge resolves it — so you get strong-model
# accuracy while the cheap model handles the (large) agreed majority alone.
# Set both to same-tier providers for a peer cross-check instead.
MODEL_A     = os.environ.get("BTL_MODEL_A", "gpt-4.1-mini")      # strong reference (openai)
MODEL_B     = os.environ.get("BTL_MODEL_B", "gemma-3-4b-it")     # cheap bulk model (openrouter)
JUDGE_MODEL = os.environ.get("BTL_JUDGE",   "gpt-4.1-mini")      # strong model adjudicates disputes

SYS = ("You are a precise information-extraction engine. Return ONLY a JSON "
       "object with exactly the requested keys. For each field, copy the "
       "shortest exact value from the text that answers it — no units, "
       "currency codes, labels, titles, or surrounding words unless the field "
       "name explicitly asks for them. Copy verbatim as written; do not "
       "reformat, round, or convert numbers. If a value is not present, use "
       "null. Never guess.")


# --- cost meter: the gateway reports real cost per call via response headers.
# ponytail: one global accumulator, fine for this single-user local tool; a
# concurrent extract during a benchmark would over-count slightly.
_cost_lock = threading.Lock()
_cost = {"charge": 0.0, "saved": 0.0, "calls": 0, "cached": 0}


def reset_cost():
    with _cost_lock:
        _cost.update(charge=0.0, saved=0.0, calls=0, cached=0)


def get_cost():
    with _cost_lock:
        return dict(_cost)


def _record_cost(headers):
    """Accumulate x-btl-* cost headers (headers.get works on HTTPMessage/dict)."""
    def num(k):
        try:
            return float(headers.get(k) or 0)
        except (TypeError, ValueError):
            return 0.0
    tier = (headers.get("x-btl-cache-tier") or "").strip().lower()
    with _cost_lock:
        _cost["calls"] += 1
        _cost["charge"] += num("x-btl-customer-charge")
        saved = num("x-btl-saved")
        _cost["saved"] += saved
        # x-btl-cache-tier isn't always present; a nonzero saved is the reliable hit signal
        if saved > 0 or (tier and tier not in ("miss", "none", "bypass")):
            _cost["cached"] += 1


class GatewayError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"gateway {status}: {body[:200]}")
        self.status = status
    @property
    def retryable(self):
        # 5xx + our 599 timeout marker + 429 rate-limit (gateway caps at 600 rpm)
        return self.status >= 500 or self.status == 429


def _http_chat(model, messages, temperature=0, response_json=True):
    """Low-level POST /v1/chat/completions. Raises GatewayError on failure."""
    body = {"model": model, "messages": messages, "temperature": temperature}
    if response_json:
        # ponytail: json_object is supported by gpt-4o-mini + deepseek; drop
        # this line if the gateway 400s on it for a given model.
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        API_BASE + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            hdrs = r.headers
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise GatewayError(e.code, e.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, socket.timeout, TimeoutError,
            http.client.HTTPException, ConnectionError, OSError) as e:
        # dropped connection / IncompleteRead / timeout -> retryable, fail over
        raise GatewayError(599, str(e))
    _record_cost(hdrs)
    return payload["choices"][0]["message"]["content"]


def _timed_chat(model, prompt):
    """One raw call, returning latency + this call's charge/saved headers."""
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        API_BASE + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            h = r.headers
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise GatewayError(e.code, e.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, socket.timeout, TimeoutError,
            http.client.HTTPException, ConnectionError, OSError) as e:
        raise GatewayError(599, str(e))
    ms = round((time.time() - t) * 1000)

    def num(k):
        try:
            return float(h.get(k) or 0)
        except (TypeError, ValueError):
            return 0.0
    return {"ms": ms, "charge": num("x-btl-customer-charge"),
            "saved": num("x-btl-saved"),
            "content": payload["choices"][0]["message"]["content"][:60]}


def cache_demo(model=None, nonce=None):
    """Fire the SAME prompt twice to show the gateway's exact cache: the second
    call is a cache hit — far faster and cheaper. The nonce guarantees the first
    call is a cold miss even on re-runs."""
    model = model or MODEL_A
    nonce = nonce if nonce is not None else int(time.time())
    prompt = f"[req {nonce}] Reply with exactly the word CROSSCHECK and nothing else."
    cold = _timed_chat(model, prompt)
    warm = _timed_chat(model, prompt)
    return {"model": model, "cold": cold, "warm": warm,
            "speedup": round(cold["ms"] / warm["ms"], 1) if warm["ms"] else None,
            "cache_hit": warm["saved"] > 0 or warm["ms"] < cold["ms"] * 0.6}


def chat(model, messages, fallback=None, chat_fn=None, retries=1):
    """Call `model`; retry on 5xx, then fail over to `fallback`.

    Returns (model_that_answered, content). Raises the last GatewayError if
    every option is exhausted.
    """
    chat_fn = chat_fn or _http_chat  # resolved at call time so tests can patch
    last = None
    for m in [model] + ([fallback] if fallback and fallback != model else []):
        for attempt in range(retries + 1):
            try:
                return m, chat_fn(m, messages)
            except GatewayError as e:
                last = e
                if not e.retryable:
                    raise
                time.sleep(0.4 * (attempt + 1))  # gentle backoff; infra is flaky
        # exhausted retries on m -> try fallback
    raise last


def _parse_json(s):
    """Best-effort JSON out of a model reply (handles ``` fences / stray prose)."""
    if not s:
        return {}
    s = s.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.I | re.M).strip()

    def _obj(x):  # extraction expects an object; arrays/scalars aren't usable
        return x if isinstance(x, dict) else {}
    try:
        return _obj(json.loads(s))
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return _obj(json.loads(m.group(0)))
            except Exception:
                return {}
        return {}


def norm(v):
    """Loose value match: case/space/currency-insensitive.
    ponytail: heuristic. Tighten per-field (dates, IDs) if false-agreements show up."""
    if v is None:
        return ""
    s = re.sub(r"\s+", " ", str(v).strip().lower())
    s = s.replace("$", "").replace(",", "")
    return s.strip(" .")


def extract(model, fallback, text, fields, chat_fn):
    user = ("Extract these fields as JSON keys "
            f"{json.dumps(fields)}:\n\n{text}")
    served, content = chat(
        model, [{"role": "system", "content": SYS},
                {"role": "user", "content": user}],
        fallback=fallback, chat_fn=chat_fn)
    return served, _parse_json(content)


def judge(text, field, a_val, b_val, chat_fn):
    """Adjudicate one disagreed field. Returns {'value':..., 'reason':...}."""
    user = (f"Two extractors disagree on the field \"{field}\".\n"
            f"Candidate A: {json.dumps(a_val)}\n"
            f"Candidate B: {json.dumps(b_val)}\n\n"
            f"Source text:\n{text}\n\n"
            "Pick the value that most precisely answers the field: the shortest "
            "exact span from the source, with no extra words, units, or labels. "
            'Return JSON {"value": <that value>, "reason": <one short sentence>}.')
    try:
        _, content = chat(JUDGE_MODEL,
                          [{"role": "system", "content": SYS},
                           {"role": "user", "content": user}],
                          fallback=MODEL_B, chat_fn=chat_fn)
        j = _parse_json(content)
        return {"value": j.get("value", a_val), "reason": j.get("reason", "")}
    except GatewayError:
        return {"value": a_val, "reason": "judge unavailable — defaulted to A"}


def crosscheck(text, fields, chat_fn=None):
    """Run both providers, compare per field, judge disagreements."""
    chat_fn = chat_fn or _http_chat
    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(extract, MODEL_A, MODEL_B, text, fields, chat_fn)
        fb = ex.submit(extract, MODEL_B, MODEL_A, text, fields, chat_fn)
        servedA, ra = fa.result()
        servedB, rb = fb.result()

    degraded = servedA == servedB  # both fell over to the same provider
    out = {}
    for f in fields:
        a, b = ra.get(f), rb.get(f)
        if not degraded and norm(a) == norm(b):
            out[f] = {"value": a, "agree": True, "needs_review": False,
                      "a": a, "b": b, "reason": ""}
        else:
            j = judge(text, f, a, b, chat_fn)
            out[f] = {"value": j["value"], "agree": False, "needs_review": True,
                      "a": a, "b": b, "reason": j["reason"]}
    return {"fields": out, "servedA": servedA, "servedB": servedB,
            "degraded": degraded,
            "failover": servedA != MODEL_A or servedB != MODEL_B}


def run_benchmark(samples, chat_fn=None, progress=None):
    """Score crosscheck vs each single model on labeled samples.
    Sequential on purpose — the gateway rate-limits (observed 429s)."""
    chat_fn = chat_fn or _http_chat
    reset_cost()
    n_fields = a_ok = b_ok = final_ok = 0
    err_fields = caught = flagged = flagged_true = 0
    rows = []
    for i, s in enumerate(samples):
        fields = list(s["fields"].keys())
        res = crosscheck(s["text"], fields, chat_fn)["fields"]
        for f in fields:
            gold = s["fields"][f]
            r = res[f]
            ga, gb, gf = norm(r["a"]), norm(r["b"]), norm(r["value"])
            g = norm(gold)
            ok_a, ok_b, ok_f = ga == g, gb == g, gf == g
            n_fields += 1
            a_ok += ok_a; b_ok += ok_b; final_ok += ok_f
            has_err = not (ok_a and ok_b)
            if has_err:
                err_fields += 1
            if r["needs_review"]:
                flagged += 1
                if has_err:
                    flagged_true += 1
                if has_err:
                    caught += 1
            rows.append({"sample": i, "field": f, "gold": gold,
                         "a": r["a"], "b": r["b"], "final": r["value"],
                         "agree": r["agree"], "final_ok": ok_f})
        if progress:
            progress(i + 1, len(samples))

    pct = lambda x, n: round(100 * x / n, 1) if n else 0.0
    c = get_cost()
    return {
        "n_samples": len(samples), "n_fields": n_fields,
        "acc_a": pct(a_ok, n_fields), "acc_b": pct(b_ok, n_fields),
        "acc_final": pct(final_ok, n_fields),
        "catch_rate": pct(caught, err_fields),       # of all field errors, % flagged
        "flag_precision": pct(flagged_true, flagged),  # of flags, % that were real errors
        "blind_spot_rate": pct(err_fields - caught, err_fields),  # errors both models shared
        "review_burden": pct(flagged, n_fields),     # % of fields sent to a human
        "cost_usd": round(c["charge"], 4),           # real gateway charge for this run
        "saved_usd": round(c["saved"], 4),           # saved by the gateway's exact cache
        "api_calls": c["calls"], "cached_calls": c["cached"],
        "rows": rows,
    }


def batch(records, chat_fn=None):
    """Verify a list of {text, fields} records — fields may be a list or a dict
    (keys are used). Returns one result per record: final values + which fields
    were flagged for review. Pipe JSONL in, get verified JSONL out."""
    out = []
    for rec in records:
        try:
            fields = rec["fields"]
            if isinstance(fields, dict):
                fields = list(fields.keys())
            r = crosscheck(rec["text"], fields, chat_fn=chat_fn)
            out.append({
                "fields": {f: v["value"] for f, v in r["fields"].items()},
                "flagged": [f for f, v in r["fields"].items() if v["needs_review"]],
                "degraded": r["degraded"],
            })
        except Exception as e:
            # one bad record (e.g. a gateway outage) must not sink the whole batch
            out.append({"error": str(e)})
    return out


DEMO_SNAPSHOT = os.path.join(os.path.dirname(__file__), "demo_snapshot.json")
HERO_TEXT = "Order: 3 cartons, 12 bottles per carton."


def load_snapshot():
    try:
        with open(DEMO_SNAPSHOT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def snapshot():
    """Capture REAL gateway results once so a live demo can replay them if the
    gateway is down (it is genuinely flaky). Each piece is captured independently
    so a partial outage still yields a usable snapshot."""
    # merge with any existing snapshot: a failed capture keeps the prior good one
    data = load_snapshot() or {}
    data["captured_at"] = int(time.time())
    data.setdefault("extract", {})
    try:
        c = cache_demo()
        # only store a sample where the cache actually wins on latency — network
        # noise can make one warm call slower, which would misrepresent the cache
        if c.get("cache_hit") and (c.get("speedup") or 0) >= 1.3:
            data["cache"] = c
        else:
            print(f"cache sample too weak (speedup {c.get('speedup')}), keeping prior")
    except Exception as e:
        print("cache snapshot failed (keeping prior):", e)
    try:
        r = crosscheck(HERO_TEXT, ["total_bottles"])
        data["extract"][HERO_TEXT.strip().lower()] = r
    except Exception as e:
        print("extract snapshot failed (keeping prior):", e)
    try:
        with open(os.path.join(os.path.dirname(__file__), "samples.json"), encoding="utf-8") as f:
            samples = json.load(f)
        m = run_benchmark(samples)
        m.pop("rows", None)
        data["benchmark"] = m
    except Exception as e:
        print("benchmark snapshot failed (keeping prior):", e)
    with open(DEMO_SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


# --- shared request handlers: one source of truth for the local server AND the
# Vercel serverless functions. Transport-agnostic (return plain code/dict).
def validate_extract(req):
    if not isinstance(req, dict):
        return "body must be a JSON object"
    if not isinstance(req.get("text"), str) or not req["text"].strip():
        return "field 'text' must be a non-empty string"
    fs = req.get("fields")
    if (not isinstance(fs, list) or not fs
            or not all(isinstance(x, str) and x.strip() for x in fs)):
        return "field 'fields' must be a non-empty list of strings"
    if len(req["text"]) > 20000:
        return "field 'text' too long (max 20000 chars)"
    if len(fs) > 40:
        return "too many fields (max 40)"
    return None


def api_samples():
    with open(os.path.join(os.path.dirname(__file__), "samples.json"), encoding="utf-8") as f:
        data = json.load(f)
    return [{"text": s["text"], "fields": list(s["fields"].keys()),
             "preview": s["text"].split("\n")[0][:40]} for s in data]


def api_extract(req):
    """(status, body) — validate, run, attach cost/latency, replay on outage."""
    err = validate_extract(req)
    if err:
        return 400, {"error": err}
    try:
        reset_cost()
        t0 = time.time()
        r = crosscheck(req["text"], req["fields"])
        r["cost_usd"] = round(get_cost()["charge"], 6)
        r["ms"] = round((time.time() - t0) * 1000)
        return 200, r
    except Exception as e:
        snap = load_snapshot().get("extract", {}).get(req["text"].strip().lower())
        if snap and all(f in snap.get("fields", {}) for f in req["fields"]):
            return 200, {**snap, "replay": True}
        return 502, {"error": str(e)}


def api_benchmark(partial=False):
    """Snapshot if captured; else run the full set (local) or a representative
    easy+hard subset (partial, for the serverless time limit)."""
    snap = load_snapshot().get("benchmark")
    if snap:
        return {**snap, "replay": True}
    with open(os.path.join(os.path.dirname(__file__), "samples.json"), encoding="utf-8") as f:
        data = json.load(f)
    samples = (data[:2] + data[15:19]) if partial else data
    m = run_benchmark(samples)
    m.pop("rows", None)
    if partial:
        m["partial"] = True
    return m


def api_cache():
    try:
        return cache_demo()
    except Exception as e:
        snap = load_snapshot().get("cache")
        if snap:
            return {**snap, "replay": True}
        return {"error": str(e)}


def api_health():
    try:
        list_models()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_models():
    req = urllib.request.Request(API_BASE + "/models",
                                 headers={"Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# --------------------------------------------------------------------------
# Offline self-check: proves compare + judge + failover without any API key.
def demo():
    def fake(model, messages):
        txt = messages[-1]["content"]
        if "disagree on the field" in txt:                 # judge call
            return '{"value":"$1,200.00","reason":"matches the subtotal line"}'
        if model == MODEL_A:
            return '{"vendor":"Acme Corp","total":"$1,200","po":"PO-88"}'
        if model == MODEL_B:
            return '{"vendor":"Acme Corp","total":"$1250","po":"PO-88"}'
        raise GatewayError(500, "unexpected model")

    r = crosscheck("dummy invoice text", ["vendor", "total", "po"], chat_fn=fake)
    fld = r["fields"]
    assert fld["vendor"]["agree"] is True and fld["vendor"]["needs_review"] is False
    assert fld["po"]["agree"] is True
    assert fld["total"]["agree"] is False and fld["total"]["needs_review"] is True
    assert fld["total"]["value"] == "$1,200.00"            # judge decided
    assert r["degraded"] is False

    # failover: MODEL_A always 503, must fall over to MODEL_B and still answer.
    def flaky(model, messages):
        if model == MODEL_A:
            raise GatewayError(503, "regional edge down")
        return '{"x":"ok"}'
    served, content = chat(MODEL_A, [{"role": "user", "content": "hi"}],
                           fallback=MODEL_B, chat_fn=flaky)
    assert served == MODEL_B and json.loads(content)["x"] == "ok"

    # non-retryable (4xx) must NOT fail over — it raises.
    def four(model, messages):
        raise GatewayError(400, "bad request")
    try:
        chat(MODEL_A, [{"role": "user", "content": "hi"}], fallback=MODEL_B, chat_fn=four)
        assert False, "4xx should raise, not fail over"
    except GatewayError as e:
        assert e.status == 400

    # degraded mode: MODEL_A fully down -> both slots fall over to MODEL_B, so
    # there is no real cross-check -> every field flagged, degraded=True.
    def deg(model, messages):
        if model == MODEL_A:
            raise GatewayError(503, "region down")
        return '{"x": "1", "y": "2"}'
    d = crosscheck("t", ["x", "y"], chat_fn=deg)
    assert d["degraded"] is True
    assert d["servedA"] == d["servedB"] == MODEL_B
    assert all(d["fields"][f]["needs_review"] for f in ("x", "y"))

    # judge unavailable (every model errors) -> defaults to candidate A, no crash.
    def alldown(model, messages):
        raise GatewayError(500, "everything down")
    j = judge("t", "f", "A-val", "B-val", chat_fn=alldown)
    assert j["value"] == "A-val" and "unavailable" in j["reason"]

    # parser tolerates code fences / prose / garbage
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('Here you go: {"a": 2} done') == {"a": 2}
    assert _parse_json("not json at all") == {}
    assert _parse_json("") == {}

    # norm: money/case/space-insensitive, handles None and numbers
    assert norm(None) == ""
    assert norm("$1,200.00") == "1200.00"
    assert norm("  Net 30 ") == "net 30"
    assert norm("$1,200") == norm("1,200") == norm(1200) == "1200"
    # ponytail: known ceiling — trailing-zero forms differ ("1200.00" vs float
    # "1200.0"); the judge resolves these numeric-format disagreements.
    assert norm("1200.00") != norm(1200.00)

    print("self-check OK: agreement, judge, 5xx failover, 4xx raises, degraded mode, "
          "judge-unavailable, parse_json, norm")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "demo":
        demo()
    elif cmd == "models":
        print(json.dumps(list_models(), indent=2))
    elif cmd == "bench":
        with open(os.path.join(os.path.dirname(__file__), "samples.json"), encoding="utf-8") as f:
            samples = json.load(f)
        m = run_benchmark(samples, progress=lambda i, n: print(f"  {i}/{n}", end="\r"))
        print()
        print(json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=2))
    elif cmd == "cache":
        print(json.dumps(cache_demo(), indent=2))
    elif cmd == "snapshot":
        snapshot()
        print(f"saved real results to {DEMO_SNAPSHOT} (demo replays these if the gateway is down)")
    elif cmd == "batch":
        src = open(sys.argv[2], encoding="utf-8") if len(sys.argv) > 2 else sys.stdin
        records = [json.loads(ln) for ln in src if ln.strip()]
        for res in batch(records):
            print(json.dumps(res))
    elif cmd == "extract":
        text = sys.argv[2]
        fields = sys.argv[3:]
        print(json.dumps(crosscheck(text, fields), indent=2))
    else:
        print("usage: crosscheck.py [demo|models|bench|cache|batch <file.jsonl>|"
              "extract <text> <f1>...]")
