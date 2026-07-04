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
            with open(os.path.join(os.path.dirname(cc.__file__), "samples.json"), encoding="utf-8") as f:
                data = json.load(f)
            out = [{"text": s["text"], "fields": list(s["fields"].keys()),
                    "preview": s["text"].split("\n")[0][:40]} for s in data]
            _send(self, 200, out)
        except Exception as e:
            _send(self, 500, {"error": str(e)})
