"""Test suite for Crosscheck — pure stdlib unittest, no pytest.

    python test_crosscheck.py            # unit + mocked-integration (no key needed)
    BTL_API_KEY=... python test_crosscheck.py   # also runs live gateway tests

Layers:
  - unit:        pure functions (norm, parse, validate, failover, compare, judge)
  - integration: the real HTTP server driven over a socket, gateway mocked
  - live:        real BTL gateway (skipped unless BTL_API_KEY is set)
"""
import os, re, io, json, http.client, threading, unittest, urllib.request, urllib.error
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
        self.assertFalse(cc.GatewayError(400).retryable)
        self.assertFalse(cc.GatewayError(404).retryable)


class TestHttpChat(unittest.TestCase):
    """_http_chat error mapping — mock urlopen, no network."""
    class _Resp:
        def __init__(self, data=None, exc=None):
            self.data, self.exc = data, exc
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
