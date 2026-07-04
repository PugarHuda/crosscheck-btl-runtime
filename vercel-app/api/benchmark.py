import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import crosscheck as cc  # noqa: E402
from http.server import BaseHTTPRequestHandler  # noqa: E402

# A full 23-sample benchmark makes ~50 gateway calls — too long for a serverless
# request. Prefer a pre-captured snapshot; otherwise run a small REPRESENTATIVE
# live subset (easy invoices + the hard reasoning cases where the cheap model errs)
# and mark it partial, so flag-precision/catch-rate are meaningful, not 0%.
# The full 23-sample number lives in the README / runs locally.
def pick(data):
    return data[:2] + data[15:19]   # 2 easy + 4 hard (incl. the 3×12→36 catch)


def _send(h, code, obj):
    b = json.dumps(obj).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(b)))
    h.end_headers()
    h.wfile.write(b)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        snap = cc.load_snapshot().get("benchmark")
        if snap:
            return _send(self, 200, {**snap, "replay": True})
        try:
            with open(os.path.join(os.path.dirname(cc.__file__), "samples.json"), encoding="utf-8") as f:
                samples = pick(json.load(f))
            m = cc.run_benchmark(samples)
            m.pop("rows", None)
            m["partial"] = True
            return _send(self, 200, m)
        except Exception as e:
            return _send(self, 200, {"error": str(e)})
