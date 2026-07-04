"""Thin dashboard for Crosscheck. Pure stdlib http.server, no framework.

    set BTL_API_KEY=...    (PowerShell: $env:BTL_API_KEY="...")
    python server.py       -> http://localhost:8000
"""
import os, json, http.server, socketserver
import crosscheck as cc

PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(__file__)

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Crosscheck · BTL Runtime</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark}
body{font:15px/1.5 system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px;max-width:920px;margin:auto}
h1{font-size:20px;margin:0 0 2px} .sub{color:#8b949e;margin:0 0 20px;font-size:13px}
textarea,select{width:100%;box-sizing:border-box;background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:8px;padding:10px;font:inherit}
textarea{height:120px;resize:vertical;font-family:ui-monospace,monospace;font-size:13px}
button{background:#238636;color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;font-weight:600;cursor:pointer;margin:8px 8px 8px 0}
button.alt{background:#21262d;border:1px solid #30363d}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.card{border:1px solid #30363d;border-radius:10px;padding:12px 14px;margin:10px 0;background:#161b22}
.ok{border-left:4px solid #3fb950} .flag{border-left:4px solid #f85149}
.k{font-weight:600} .v{font-size:17px;margin:2px 0}
.mini{color:#8b949e;font-size:12px;font-family:ui-monospace,monospace}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;margin-left:8px}
.b-ok{background:#12361f;color:#3fb950} .b-flag{background:#3d1418;color:#f85149}
.banner{padding:10px 14px;border-radius:8px;margin:10px 0;font-size:13px}
.warn{background:#3d2c05;border:1px solid #9e6a03;color:#f2cc60}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.stat{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center}
.stat b{font-size:26px;display:block;color:#58a6ff} .stat span{font-size:12px;color:#8b949e}
.hl b{color:#3fb950}
.reason{color:#8b949e;font-size:12px;margin-top:4px;font-style:italic}
</style></head><body>
<h1>Crosscheck <span class=mini>· reliability layer on the BTL runtime</span></h1>
<p class=sub>Same prompt &rarr; two providers in parallel. Agree = auto-accept. Disagree = judge + flag. One provider down = fail over.</p>

<select id=sample></select>
<textarea id=text placeholder="Paste messy text..."></textarea>
<input id=fields style="width:100%;box-sizing:border-box;background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:8px;padding:10px;margin-top:8px" placeholder="fields, comma separated e.g. vendor, invoice_no, total">
<div class=row>
  <button onclick=run()>Run Crosscheck</button>
  <button class=alt onclick=bench()>Run Benchmark</button>
  <span id=status class=mini></span>
</div>
<div id=out></div>
<div id=benchout></div>
<script>
let SAMPLES=[];
fetch('/api/samples').then(r=>r.json()).then(d=>{SAMPLES=d;
  const s=document.getElementById('sample');
  s.innerHTML='<option value=-1>— pick a sample or paste your own —</option>'+
    d.map((x,i)=>`<option value=${i}>Sample ${i+1}: ${x.preview}</option>`).join('');
  s.onchange=()=>{const i=+s.value;if(i<0)return;
    document.getElementById('text').value=SAMPLES[i].text;
    document.getElementById('fields').value=SAMPLES[i].fields.join(', ');};
});
function run(){
  const text=document.getElementById('text').value;
  const fields=document.getElementById('fields').value.split(',').map(x=>x.trim()).filter(Boolean);
  if(!text||!fields.length){alert('need text + fields');return;}
  document.getElementById('status').textContent='calling two providers…';
  document.getElementById('out').innerHTML='';
  fetch('/api/extract',{method:'POST',body:JSON.stringify({text,fields})})
   .then(r=>r.json()).then(render).catch(e=>document.getElementById('status').textContent='error: '+e);
}
function render(d){
  document.getElementById('status').textContent='';
  let h='';
  if(d.error){document.getElementById('out').innerHTML=`<div class="banner warn">gateway error: ${d.error}</div>`;return;}
  if(d.degraded) h+=`<div class="banner warn">⚠ Degraded: both requests served by <b>${d.servedA}</b> — the other provider failed over. Cross-check disabled, all fields flagged.</div>`;
  else if(d.servedA!=d.servedB && d.failover) h+=`<div class="banner warn">↺ Failover engaged mid-run.</div>`;
  h+=`<p class=mini>served by ${d.servedA} + ${d.servedB}</p>`;
  for(const f in d.fields){const x=d.fields[f];
    h+=`<div class="card ${x.agree?'ok':'flag'}">
      <div class=k>${f}
        <span class="badge ${x.agree?'b-ok':'b-flag'}">${x.agree?'agreed':'needs review'}</span></div>
      <div class=v>${fmt(x.value)}</div>
      <div class=mini>A(${d.servedA}): ${fmt(x.a)} &nbsp;|&nbsp; B(${d.servedB}): ${fmt(x.b)}</div>
      ${x.reason?`<div class=reason>judge: ${x.reason}</div>`:''}
    </div>`;}
  document.getElementById('out').innerHTML=h;
}
function fmt(v){return v==null?'<i>null</i>':String(v);}
function bench(){
  document.getElementById('status').textContent='benchmarking (this hits the API many times)…';
  document.getElementById('benchout').innerHTML='';
  fetch('/api/benchmark').then(r=>r.json()).then(m=>{
    document.getElementById('status').textContent='';
    if(m.error){document.getElementById('benchout').innerHTML=`<div class="banner warn">${m.error}</div>`;return;}
    document.getElementById('benchout').innerHTML=`
    <div class=grid>
      <div class=stat><b>${m.acc_a}%</b><span>${m.n_fields} fields · Model A alone</span></div>
      <div class=stat><b>${m.acc_b}%</b><span>Model B alone</span></div>
      <div class=stat><b>${m.acc_final}%</b><span>Crosscheck consensus</span></div>
    </div>
    <div class=grid>
      <div class="stat hl"><b>${m.flag_precision}%</b><span>flag precision (real discrepancies)</span></div>
      <div class="stat hl"><b>${m.review_burden}%</b><span>of fields sent to a human</span></div>
      <div class=stat><b>${m.catch_rate}%</b><span>of errors flagged</span></div>
      <div class=stat><b>${m.blind_spot_rate}%</b><span>blind spot (providers shared the bias)</span></div>
    </div>
    <p class=mini>${m.n_samples} samples. Honest: two strong models mostly agree, so consensus accuracy ≈ the best single model — the win is the confidence signal + failover, not raw accuracy. Blind spot (shared bias) is reported, not hidden.</p>`;
  }).catch(e=>document.getElementById('status').textContent='error: '+e);
}
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/samples":
            with open(os.path.join(HERE, "samples.json"), encoding="utf-8") as f:
                data = json.load(f)
            out = [{"text": s["text"], "fields": list(s["fields"].keys()),
                    "preview": s["text"].split("\n")[0][:40]} for s in data]
            return self._send(200, json.dumps(out))
        if self.path == "/api/benchmark":
            try:
                with open(os.path.join(HERE, "samples.json"), encoding="utf-8") as f:
                    samples = json.load(f)
                m = cc.run_benchmark(samples)
                m.pop("rows", None)
                return self._send(200, json.dumps(m))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/extract":
            return self._send(404, json.dumps({"error": "not found"}))
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            r = cc.crosscheck(req["text"], req["fields"])
            return self._send(200, json.dumps(r))
        except Exception as e:
            return self._send(200, json.dumps({"error": str(e)}))


if __name__ == "__main__":
    if not cc.API_KEY:
        print("WARNING: BTL_API_KEY not set — API calls will 401.")
    print(f"Crosscheck dashboard: http://localhost:{PORT}  (Ctrl+C to stop)")
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), H) as srv:
        srv.serve_forever()
