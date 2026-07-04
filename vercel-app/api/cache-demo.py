import os, sys, json
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
    def do_GET(self):
        try:
            _send(self, 200, cc.cache_demo())
        except Exception as e:
            snap = cc.load_snapshot().get("cache")
            if snap:
                return _send(self, 200, {**snap, "replay": True})
            _send(self, 200, {"error": str(e)})
