import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import crosscheck as cc  # noqa: E402
from http.server import BaseHTTPRequestHandler  # noqa: E402


def _send(h, code, obj):
    b = json.dumps(obj).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(b)))
    h.end_headers()
    h.wfile.write(b)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return _send(self, 400, {"error": "invalid JSON body"})
        if not isinstance(req, dict) or not isinstance(req.get("text"), str) or not req["text"].strip():
            return _send(self, 400, {"error": "field 'text' must be a non-empty string"})
        fs = req.get("fields")
        if (not isinstance(fs, list) or not fs
                or not all(isinstance(x, str) and x.strip() for x in fs)):
            return _send(self, 400, {"error": "field 'fields' must be a non-empty list of strings"})
        if len(req["text"]) > 20000 or len(fs) > 40:
            return _send(self, 400, {"error": "input too large"})
        try:
            cc.reset_cost()
            t0 = time.time()
            r = cc.crosscheck(req["text"], fs)
            r["cost_usd"] = round(cc.get_cost()["charge"], 6)
            r["ms"] = round((time.time() - t0) * 1000)
            return _send(self, 200, r)
        except Exception as e:
            snap = cc.load_snapshot().get("extract", {}).get(req["text"].strip().lower())
            if snap and all(f in snap.get("fields", {}) for f in fs):
                return _send(self, 200, {**snap, "replay": True})
            return _send(self, 502, {"error": str(e)})
