"""Test suite for Crosscheck — pure stdlib unittest, no pytest.

    python test_crosscheck.py            # unit + mocked-integration (no key needed)
    BTL_API_KEY=... python test_crosscheck.py   # also runs live gateway tests

Layers:
  - unit:        pure functions (norm, parse, validate, failover, compare, judge)
  - integration: the real HTTP server driven over a socket, gateway mocked
  - live:        real BTL gateway (skipped unless BTL_API_KEY is set)
"""
import os, re, io, json, http.client, threading, tempfile, unittest, urllib.request, urllib.error
from unittest import mock
import socketserver

import crosscheck as cc
import server


# --- a deterministic fake gateway ----------------------------------------
def fake_gateway(model, messages):
    """Extraction: every requested field -> 'VAL' (both models agree).
    Judge: returns a fixed resolved value."""
    txt = messages[-1]["content"]
    if "disagree on the field" in txt:
        return '{"value": "RESOLVED", "reason": "test"}'
    m = re.search(r"\[.*\]", txt)
    fields = json.loads(m.group(0)) if m else []
    return json.dumps({f: "VAL" for f in fields})


# ========================= UNIT: pure helpers ============================
class TestNorm(unittest.TestCase):
    def test_none_and_blank(self):
        self.assertEqual(cc.norm(None), "")
        self.assertEqual(cc.norm("   "), "")

    def test_money_case_space(self):
        self.assertEqual(cc.norm("$1,200.00"), "1200.00")
        self.assertEqual(cc.norm("  Net 30 "), "net 30")
        self.assertEqual(cc.norm("$1,200"), cc.norm("1,200"))
        self.assertEqual(cc.norm(1200), "1200")

    def test_trailing_zero_ceiling(self):
        # documented heuristic limitation, not a bug
        self.assertNotEqual(cc.norm("1200.00"), cc.norm(1200.00))


class TestParseJson(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(cc._parse_json('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        self.assertEqual(cc._parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_wrapped(self):
        self.assertEqual(cc._parse_json('Sure: {"a": 2} done'), {"a": 2})

    def test_garbage_and_empty(self):
        self.assertEqual(cc._parse_json("not json"), {})
        self.assertEqual(cc._parse_json(""), {})

    def test_non_object_coerced(self):
        # array / scalar responses must not become non-dicts (would crash .get)
        self.assertEqual(cc._parse_json("[1, 2, 3]"), {})
        self.assertEqual(cc._parse_json('"just a string"'), {})
        self.assertEqual(cc._parse_json("42"), {})


class TestValidate(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(server.validate_extract({"text": "hi", "fields": ["a"]}))

    def test_bad_bodies(self):
        self.assertIn("object", server.validate_extract("nope"))
        self.assertIn("text", server.validate_extract({"fields": ["a"]}))
        self.assertIn("text", server.validate_extract({"text": " ", "fields": ["a"]}))
        self.assertIn("fields", server.validate_extract({"text": "hi"}))
        self.assertIn("fields", server.validate_extract({"text": "hi", "fields": []}))
        self.assertIn("fields", server.validate_extract({"text": "hi", "fields": "a"}))
        self.assertIn("fields", server.validate_extract({"text": "hi", "fields": ["a", ""]}))

    def test_size_caps(self):
        self.assertIn("too long", server.validate_extract(
            {"text": "x" * 20001, "fields": ["a"]}))
        self.assertIn("too many", server.validate_extract(
            {"text": "hi", "fields": [f"f{i}" for i in range(41)]}))


class TestGatewayError(unittest.TestCase):
    def test_retryable(self):
        self.assertTrue(cc.GatewayError(500).retryable)
        self.assertTrue(cc.GatewayError(599).retryable)
        self.assertTrue(cc.GatewayError(429).retryable)   # rate limit -> retry
        self.assertFalse(cc.GatewayError(400).retryable)
        self.assertFalse(cc.GatewayError(404).retryable)


class TestHttpChat(unittest.TestCase):
    """_http_chat error mapping — mock urlopen, no network."""
    class _Resp:
        def __init__(self, data=None, exc=None):
            self.data, self.exc, self.headers = data, exc, {}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a):
            if self.exc:
                raise self.exc
            return self.data

    def test_success(self):
        body = b'{"choices": [{"message": {"content": "hi"}}]}'
        with mock.patch("urllib.request.urlopen", return_value=self._Resp(body)):
            self.assertEqual(cc._http_chat("m", [{"role": "user", "content": "x"}]), "hi")

    def test_httperror_maps_status(self):
        err = urllib.error.HTTPError("u", 503, "down", {}, io.BytesIO(b"boom"))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(cc.GatewayError) as e:
                cc._http_chat("m", [{"role": "user", "content": "x"}])
        self.assertEqual(e.exception.status, 503)
        self.assertTrue(e.exception.retryable)

    def test_urlerror_is_599(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("nope")):
            with self.assertRaises(cc.GatewayError) as e:
                cc._http_chat("m", [{"role": "user", "content": "x"}])
        self.assertEqual(e.exception.status, 599)

    def test_incomplete_read_regression(self):
        # dropped connection mid-read must map to retryable 599, not crash
        exc = http.client.IncompleteRead(b"", 5)
        with mock.patch("urllib.request.urlopen", return_value=self._Resp(exc=exc)):
            with self.assertRaises(cc.GatewayError) as e:
                cc._http_chat("m", [{"role": "user", "content": "x"}])
        self.assertEqual(e.exception.status, 599)
        self.assertTrue(e.exception.retryable)


# ==================== UNIT: failover / orchestration =====================
class TestFailover(unittest.TestCase):
    def test_primary_ok(self):
        served, _ = cc.chat("A", [], fallback="B", chat_fn=lambda m, x: "ok")
        self.assertEqual(served, "A")

    def test_5xx_fails_over(self):
        def f(m, x):
            if m == "A":
                raise cc.GatewayError(503)
            return "ok"
        served, out = cc.chat("A", [], fallback="B", chat_fn=f)
        self.assertEqual(served, "B")
        self.assertEqual(out, "ok")

    def test_4xx_raises_no_failover(self):
        def f(m, x):
            raise cc.GatewayError(400)
        with self.assertRaises(cc.GatewayError) as e:
            cc.chat("A", [], fallback="B", chat_fn=f)
        self.assertEqual(e.exception.status, 400)

    def test_429_fails_over(self):
        def f(m, x):
            if m == "A":
                raise cc.GatewayError(429)
            return "ok"
        served, _ = cc.chat("A", [], fallback="B", chat_fn=f)
        self.assertEqual(served, "B")


class TestCrosscheckUnit(unittest.TestCase):
    def test_agreement(self):
        def f(m, x):
            return '{"v": "same"}'
        r = cc.crosscheck("t", ["v"], chat_fn=f)["fields"]["v"]
        self.assertTrue(r["agree"])
        self.assertFalse(r["needs_review"])
        self.assertEqual(r["value"], "same")

    def test_disagreement_triggers_judge(self):
        def f(m, x):
            if "disagree on the field" in x[-1]["content"]:
                return '{"value": "JUDGED", "reason": "r"}'
            return ('{"v": "A"}' if m == cc.MODEL_A else '{"v": "B"}')
        r = cc.crosscheck("t", ["v"], chat_fn=f)["fields"]["v"]
        self.assertFalse(r["agree"])
        self.assertTrue(r["needs_review"])
        self.assertEqual(r["value"], "JUDGED")

    def test_degraded_when_primary_down(self):
        def f(m, x):
            if m == cc.MODEL_A:
                raise cc.GatewayError(503)
            return '{"x": "1", "y": "2"}'
        r = cc.crosscheck("t", ["x", "y"], chat_fn=f)
        self.assertTrue(r["degraded"])
        self.assertTrue(r["failover"])
        self.assertEqual(r["servedA"], r["servedB"])
        self.assertTrue(all(r["fields"][k]["needs_review"] for k in ("x", "y")))

    def test_no_failover_flag_when_both_primary(self):
        r = cc.crosscheck("t", ["v"], chat_fn=lambda m, x: '{"v": "1"}')
        self.assertFalse(r["failover"])
        self.assertFalse(r["degraded"])

    def test_array_response_does_not_crash(self):
        # model returns a JSON array instead of an object -> fields become None,
        # no AttributeError
        r = cc.crosscheck("t", ["v"], chat_fn=lambda m, x: "[1, 2, 3]")
        self.assertIn("v", r["fields"])
        self.assertIsNone(r["fields"]["v"]["value"])


class TestJudge(unittest.TestCase):
    def test_unavailable_defaults_to_a(self):
        def down(m, x):
            raise cc.GatewayError(500)
        j = cc.judge("t", "f", "A-val", "B-val", chat_fn=down)
        self.assertEqual(j["value"], "A-val")
        self.assertIn("unavailable", j["reason"])


class TestBenchmarkScoring(unittest.TestCase):
    def test_counts_and_accuracy(self):
        # one sample, one field; both models say "36" (correct) -> all accurate
        samples = [{"text": "3 x 12", "fields": {"n": "36"}}]
        def f(m, x):
            return '{"n": "36"}'
        m = cc.run_benchmark(samples, chat_fn=f)
        self.assertEqual(m["n_samples"], 1)
        self.assertEqual(m["n_fields"], 1)
        self.assertEqual(m["acc_a"], 100.0)
        self.assertEqual(m["acc_final"], 100.0)

    def test_flag_precision_on_caught_error(self):
        # models disagree; cheap(B) wrong, strong(A)+judge right -> flagged, precise
        samples = [{"text": "q", "fields": {"n": "36"}}]
        def f(m, x):
            if "disagree on the field" in x[-1]["content"]:
                return '{"value": "36", "reason": "r"}'
            return ('{"n": "36"}' if m == cc.MODEL_A else '{"n": "12"}')
        m = cc.run_benchmark(samples, chat_fn=f)
        self.assertEqual(m["flag_precision"], 100.0)
        self.assertEqual(m["review_burden"], 100.0)   # the one field was flagged
        self.assertEqual(m["acc_final"], 100.0)        # judge fixed it


class TestCost(unittest.TestCase):
    def test_record_reset_and_cache_count(self):
        cc.reset_cost()
        cc._record_cost({"x-btl-customer-charge": "0.0022", "x-btl-saved": "0.001",
                         "x-btl-cache-tier": "exact_response_cache"})
        cc._record_cost({"x-btl-customer-charge": "0.0010", "x-btl-saved": "0",
                         "x-btl-cache-tier": "miss"})
        c = cc.get_cost()
        self.assertAlmostEqual(c["charge"], 0.0032)
        self.assertAlmostEqual(c["saved"], 0.001)
        self.assertEqual(c["calls"], 2)
        self.assertEqual(c["cached"], 1)   # one hit, one miss
        cc.reset_cost()
        self.assertEqual(cc.get_cost()["calls"], 0)

    def test_missing_headers_are_zero(self):
        cc.reset_cost()
        cc._record_cost({})
        c = cc.get_cost()
        self.assertEqual(c["calls"], 1)
        self.assertEqual(c["charge"], 0.0)

    def test_benchmark_reports_cost_keys(self):
        m = cc.run_benchmark([{"text": "q", "fields": {"n": "1"}}],
                             chat_fn=lambda mm, x: '{"n": "1"}')
        for k in ("cost_usd", "saved_usd", "api_calls", "cached_calls"):
            self.assertIn(k, m)


class TestBatch(unittest.TestCase):
    def test_list_and_dict_fields(self):
        recs = [{"text": "t", "fields": ["a"]},
                {"text": "u", "fields": {"b": "x"}}]  # dict -> keys used
        out = cc.batch(recs, chat_fn=lambda m, x: '{"a": "1", "b": "2"}')
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["fields"]["a"], "1")
        self.assertEqual(out[1]["fields"]["b"], "2")
        self.assertIn("flagged", out[0])
        self.assertIn("degraded", out[0])

    def test_flagged_on_disagreement(self):
        def f(m, x):
            if "disagree on the field" in x[-1]["content"]:
                return '{"value": "36", "reason": "r"}'
            return ('{"n": "36"}' if m == cc.MODEL_A else '{"n": "12"}')
        out = cc.batch([{"text": "q", "fields": ["n"]}], chat_fn=f)
        self.assertEqual(out[0]["flagged"], ["n"])

    def test_bad_record_isolated(self):
        def f(m, x):
            raise cc.GatewayError(400)   # non-retryable -> raises fast
        out = cc.batch([{"text": "a", "fields": ["x"]},
                        {"text": "b", "fields": ["y"]}], chat_fn=f)
        self.assertEqual(len(out), 2)          # both recorded, batch didn't crash
        self.assertIn("error", out[0])
        self.assertIn("error", out[1])


class TestSnapshot(unittest.TestCase):
    def test_load_missing_returns_empty(self):
        old = cc.DEMO_SNAPSHOT
        cc.DEMO_SNAPSHOT = os.path.join(tempfile.gettempdir(), "does_not_exist_xyz.json")
        try:
            self.assertEqual(cc.load_snapshot(), {})
        finally:
            cc.DEMO_SNAPSHOT = old

    def test_merge_keeps_prior_when_capture_fails(self):
        # regression: a failed capture must NOT wipe previously captured pieces
        fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
        prior = {"cache": {"speedup": 2.0}, "extract": {"k": {"v": 1}},
                 "benchmark": {"acc_final": 90}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prior, f)
        old = cc.DEMO_SNAPSHOT
        cc.DEMO_SNAPSHOT = path
        try:
            with mock.patch.object(cc, "cache_demo", side_effect=cc.GatewayError(500)), \
                 mock.patch.object(cc, "crosscheck", side_effect=cc.GatewayError(500)), \
                 mock.patch.object(cc, "run_benchmark", side_effect=cc.GatewayError(500)):
                cc.snapshot()
            with open(path, encoding="utf-8") as f:
                after = json.load(f)
            self.assertEqual(after["cache"]["speedup"], 2.0)
            self.assertEqual(after["extract"]["k"], {"v": 1})
            self.assertEqual(after["benchmark"]["acc_final"], 90)
        finally:
            cc.DEMO_SNAPSHOT = old
            os.unlink(path)


class TestApiLayer(unittest.TestCase):
    """Direct tests for the shared request handlers (used by both server.py and the
    Vercel serverless functions) — the refactor's single source of truth."""
    OK_RESULT = {"fields": {"a": {"value": "1", "agree": True, "needs_review": False,
                                  "a": "1", "b": "1", "reason": ""}},
                 "servedA": "m", "servedB": "m", "degraded": False, "failover": False}

    def test_extract_rejects_bad_input(self):
        self.assertEqual(cc.api_extract({"text": ""})[0], 400)
        self.assertEqual(cc.api_extract({"text": "hi", "fields": []})[0], 400)
        self.assertEqual(cc.api_extract("nope")[0], 400)

    def test_extract_ok_attaches_cost_and_ms(self):
        with mock.patch.object(cc, "crosscheck", return_value=dict(self.OK_RESULT)):
            code, obj = cc.api_extract({"text": "t", "fields": ["a"]})
        self.assertEqual(code, 200)
        self.assertIn("cost_usd", obj)
        self.assertIn("ms", obj)

    def test_extract_replays_on_outage(self):
        fake = {"extract": {"t": {"fields": {"a": {"value": "c"}}}}}
        with mock.patch.object(cc, "crosscheck", side_effect=cc.GatewayError(500)), \
             mock.patch.object(cc, "load_snapshot", return_value=fake):
            code, obj = cc.api_extract({"text": "t", "fields": ["a"]})
        self.assertEqual(code, 200)
        self.assertTrue(obj.get("replay"))

    def test_benchmark_partial_uses_representative_subset(self):
        allkeys = ('{"vendor":"x","invoice_no":"x","total":"x","terms":"x","merchant":"x",'
                   '"order_no":"x","amount":"x","card_last4":"x","subtotal":"x",'
                   '"total_bottles":"x","due_date":"x","seats_left":"x"}')
        with mock.patch.object(cc, "load_snapshot", return_value={}), \
             mock.patch.object(cc, "_http_chat", lambda m, x: allkeys):
            m = cc.api_benchmark(partial=True)
        self.assertTrue(m.get("partial"))
        self.assertEqual(m["n_samples"], 6)   # 2 easy + 4 hard

    def test_health_ok_and_down(self):
        with mock.patch.object(cc, "list_models", return_value={"data": []}):
            self.assertTrue(cc.api_health()["ok"])
        with mock.patch.object(cc, "list_models", side_effect=cc.GatewayError(500)):
            self.assertFalse(cc.api_health()["ok"])

    def test_crosscheck_honors_chosen_models(self):
        r = cc.crosscheck("t", ["a"], chat_fn=lambda m, x: '{"a": "1"}',
                          models=("model-x", "model-y"))
        self.assertEqual({r["servedA"], r["servedB"]}, {"model-x", "model-y"})

    def test_extract_rejects_bad_models(self):
        self.assertEqual(cc.api_extract({"text": "t", "fields": ["a"],
                                         "models": ["only-one"]})[0], 400)
        self.assertEqual(cc.api_extract({"text": "t", "fields": ["a"],
                                         "models": "x"})[0], 400)

    def test_api_models_shape(self):
        with mock.patch.object(cc, "list_models",
                               return_value={"data": [{"id": "gpt-4.1-mini"},
                                                      {"id": "gemma-3-4b-it"}]}):
            d = cc.api_models()
        self.assertIn("gpt-4.1-mini", d["models"])
        self.assertEqual(d["default_a"], cc.MODEL_A)


class TestDeployAssets(unittest.TestCase):
    """Guard the untested deploy glue: serverless functions must at least compile,
    and the web assets the deploy assembles from must exist."""
    ROOT = os.path.dirname(os.path.abspath(__file__))

    def test_serverless_functions_compile(self):
        import py_compile, glob
        fns = glob.glob(os.path.join(self.ROOT, "vercel-app", "api", "*.py"))
        self.assertGreaterEqual(len(fns), 5)
        for f in fns:
            py_compile.compile(f, doraise=True)   # raises PyCompileError on syntax error

    def test_web_assets_exist(self):
        for f in ("web/index.html", "web/404.html", "vercel-app/vercel.json"):
            self.assertTrue(os.path.exists(os.path.join(self.ROOT, f)), f + " missing")


# ================= INTEGRATION: real HTTP server, mocked gateway =========
class TestServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher = mock.patch.object(cc, "_http_chat", fake_gateway)
        cls.patcher.start()
        cls.srv = socketserver.ThreadingTCPServer(("localhost", 0), server.H)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.patcher.stop()

    def _get(self, path):
        with urllib.request.urlopen(f"http://localhost:{self.port}{path}") as r:
            return r.status, r.read()

    def _post(self, path, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(f"http://localhost:{self.port}{path}", data=data)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_home_html(self):
        code, body = self._get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"<title>Crosscheck", body)

    def test_samples(self):
        code, body = self._get("/api/samples")
        self.assertEqual(code, 200)
        self.assertGreater(len(json.loads(body)), 0)

    def test_benchmark_endpoint(self):
        code, body = self._get("/api/benchmark")
        self.assertEqual(code, 200)
        m = json.loads(body)
        for k in ("n_samples", "acc_a", "acc_b", "acc_final", "flag_precision"):
            self.assertIn(k, m)

    def test_unknown_get_404(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self._get("/api/nope")
        self.assertEqual(e.exception.code, 404)

    def test_extract_valid(self):
        code, body = self._post("/api/extract", {"text": "t", "fields": ["a", "b"]})
        self.assertEqual(code, 200)
        self.assertEqual(set(body["fields"]), {"a", "b"})
        self.assertTrue(body["fields"]["a"]["agree"])
        self.assertIn("cost_usd", body)   # per-request cost + latency attached
        self.assertIn("ms", body)

    def test_health(self):
        with mock.patch.object(cc, "list_models", return_value={"data": []}):
            code, body = self._get("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_extract_bad_json(self):
        code, body = self._post("/api/extract", b"not json")
        self.assertEqual(code, 400)
        self.assertIn("JSON", body["error"])

    def test_extract_missing_fields(self):
        code, body = self._post("/api/extract", {"text": "hi"})
        self.assertEqual(code, 400)
        self.assertIn("fields", body["error"])

    def test_post_unknown_404(self):
        code, body = self._post("/api/nope", {})
        self.assertEqual(code, 404)

    def test_extract_replays_snapshot_when_gateway_down(self):
        fake = {"extract": {"boom": {
            "fields": {"a": {"value": "cached", "agree": True, "needs_review": False,
                             "a": "cached", "b": "cached", "reason": ""}},
            "servedA": "m", "servedB": "m", "degraded": False, "failover": False}}}
        with mock.patch.object(cc, "crosscheck", side_effect=cc.GatewayError(500)), \
             mock.patch.object(cc, "load_snapshot", return_value=fake):
            code, body = self._post("/api/extract", {"text": "boom", "fields": ["a"]})
        self.assertEqual(code, 200)
        self.assertTrue(body.get("replay"))
        self.assertEqual(body["fields"]["a"]["value"], "cached")

    def test_no_snapshot_still_502s(self):
        with mock.patch.object(cc, "crosscheck", side_effect=cc.GatewayError(500)), \
             mock.patch.object(cc, "load_snapshot", return_value={}):
            code, body = self._post("/api/extract", {"text": "x", "fields": ["a"]})
        self.assertEqual(code, 502)


# ============================ LIVE: real gateway =========================
@unittest.skipUnless(os.environ.get("BTL_API_KEY"), "set BTL_API_KEY for live tests")
class TestLiveGateway(unittest.TestCase):
    """Hits the real gateway. It is genuinely flaky (intermittent 500s), so a
    persistent 5xx skips the test rather than failing it — we're verifying OUR
    integration, not the gateway's uptime."""

    def _live(self, fn, tries=3):
        import time
        last = None
        for i in range(tries):
            try:
                return fn()
            except cc.GatewayError as e:
                last = e
                if e.status >= 500:
                    time.sleep(1.0 * (i + 1))
                    continue
                raise
        self.skipTest(f"gateway unavailable after {tries} tries ({last})")

    def test_models_listed(self):
        data = self._live(cc.list_models)["data"]
        ids = {m["id"] for m in data}
        self.assertIn(cc.MODEL_A, ids)
        self.assertIn(cc.MODEL_B, ids)

    def test_real_extraction(self):
        r = self._live(lambda: cc.crosscheck(
            "Invoice #AR-2291 total $1,036.80", ["invoice_no", "total"]))
        self.assertEqual(set(r["fields"]), {"invoice_no", "total"})
        self.assertEqual(cc.norm(r["fields"]["invoice_no"]["value"]), "ar-2291")

    def test_real_catch(self):
        # cheap model tends to misread this; strong model + judge should land 36
        r = self._live(lambda: cc.crosscheck(
            "Order: 3 cartons, 12 bottles per carton.", ["total_bottles"]))
        self.assertEqual(cc.norm(r["fields"]["total_bottles"]["value"]), "36")

    def test_cache_demo_hits(self):
        d = self._live(lambda: cc.cache_demo())
        self.assertGreater(d["cold"]["ms"], 0)
        self.assertGreaterEqual(d["warm"]["saved"], 0)
        self.assertTrue(d["cache_hit"])  # 2nd identical call is cheaper or faster


if __name__ == "__main__":
    unittest.main(verbosity=2)
