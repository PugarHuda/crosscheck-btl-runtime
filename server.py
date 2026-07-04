"""Thin dashboard for Crosscheck. Pure stdlib http.server, no framework.

    set BTL_API_KEY=...    (PowerShell: $env:BTL_API_KEY="...")
    python server.py       -> http://localhost:8000
"""
import os, sys, time, json, http.server, socketserver
import crosscheck as cc


def validate_extract(req):
    """Return an error string for a bad /api/extract body, or None if valid."""
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

PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(__file__)
SNAP = cc.load_snapshot()  # real captured results; replayed if the gateway is down

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Crosscheck · BTL Runtime</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;
  --ink:#0a0f1e;--panel:#121826;--panel2:#0d1320;--line:#232c3e;--text:#e8edf6;
  --muted:#8b97ad;--accent:#4c8dff;--good:#35c07f;--flag:#ff5c57;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  --serif:Georgia,"Times New Roman",serif}
*{box-sizing:border-box}
body{font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--ink);
  color:var(--text);margin:0;padding:clamp(6px,1.4vw,14px)}
.frame{max-width:960px;margin:0 auto;background:var(--panel2);border:1px solid var(--line);border-radius:4px}
.pad{padding:clamp(18px,3vw,30px)}
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;
  padding:14px clamp(18px,3vw,26px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:-.01em;font-size:17px}
.mark{width:22px;height:22px;flex:none;color:var(--text)}
.toplinks{display:flex;align-items:center;gap:16px;font-family:var(--mono);font-size:12px;color:var(--muted)}
.toplinks a{color:var(--muted);text-decoration:none} .toplinks a:hover{color:var(--text)}
.dot{width:8px;height:8px;border-radius:50%;background:#5b6472;display:inline-block;margin-right:6px;vertical-align:middle}
.dot.up{background:var(--good);box-shadow:0 0 0 3px color-mix(in srgb,var(--good) 22%,transparent)}
.dot.down{background:var(--flag);box-shadow:0 0 0 3px color-mix(in srgb,var(--flag) 22%,transparent)}
.heroline{font-family:var(--mono);text-transform:uppercase;font-size:clamp(19px,3vw,27px);
  letter-spacing:-.01em;margin:0 0 6px;font-weight:600}
.heroline em{font-family:var(--serif);font-style:italic;text-transform:none;font-weight:500;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 20px;font-size:13.5px;max-width:70ch}
textarea,select,#fields{width:100%;background:var(--panel);color:var(--text);border:1px solid var(--line);
  border-radius:8px;padding:10px;font:inherit;margin-top:8px}
textarea{height:110px;resize:vertical;font-family:var(--mono);font-size:13px}
#fields{font-family:var(--mono);font-size:13px}
select{font-family:var(--mono);font-size:12.5px}
button{background:var(--accent);color:#04102b;border:0;border-radius:8px;padding:9px 16px;font:inherit;
  font-weight:600;cursor:pointer;margin:10px 8px 0 0}
button.alt{background:var(--panel);border:1px solid var(--line);color:var(--text)}
button:hover{filter:brightness(1.08)} button:disabled{opacity:.5;cursor:progress;filter:none}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.summary{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;
  color:var(--muted);margin:14px 0 6px}
.summary .copy{margin-left:auto;background:var(--panel);border:1px solid var(--line);color:var(--text);
  border-radius:6px;padding:5px 11px;font-family:var(--mono);font-size:11px;cursor:pointer}
.summary .copy:hover{border-color:var(--accent)}
.card{border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:11px 14px;margin:9px 0;background:var(--panel)}
.ok{border-left-color:var(--good)} .flag{border-left-color:var(--flag)}
.k{font-weight:600;font-family:var(--mono);font-size:13px}
.v{font-size:18px;margin:3px 0;font-family:var(--mono);font-variant-numeric:tabular-nums}
.mini{color:var(--muted);font-size:12px;font-family:var(--mono)}
.badge{font-size:10px;padding:2px 8px;border-radius:20px;margin-left:8px;font-family:var(--mono);letter-spacing:.04em;text-transform:uppercase}
.b-ok{background:color-mix(in srgb,var(--good) 15%,transparent);color:var(--good)}
.b-flag{background:color-mix(in srgb,var(--flag) 15%,transparent);color:var(--flag)}
.banner{padding:10px 14px;border-radius:8px;margin:10px 0;font-size:13px;font-family:var(--mono)}
.warn{background:#241a06;border:1px solid #7a5310;color:#f2cc60}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;text-align:center}
.stat b{font-size:25px;display:block;font-family:var(--mono);font-variant-numeric:tabular-nums}
.stat span{font-size:11px;color:var(--muted);font-family:var(--mono)}
.hl b{color:var(--accent)}
.reason{color:var(--muted);font-size:12px;margin-top:4px;font-style:italic}
</style>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%234c8dff'%3E%3Crect x='2' y='2' width='6' height='6'/%3E%3Crect x='16' y='2' width='6' height='6'/%3E%3Crect x='9' y='9' width='6' height='6'/%3E%3Crect x='2' y='16' width='6' height='6'/%3E%3Crect x='16' y='16' width='6' height='6'/%3E%3C/svg%3E">
</head><body>
<div class=frame>
  <div class=top>
    <div class=brand>
      <svg class=mark viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x=2 y=2 width=6 height=6/><rect x=16 y=2 width=6 height=6/><rect x=9 y=9 width=6 height=6/><rect x=2 y=16 width=6 height=6/><rect x=16 y=16 width=6 height=6/></svg>
      crosscheck.
    </div>
    <div class=toplinks>
      <span id=health title="checking gateway…"><span class=dot id=dot></span>gateway</span>
      <a href="https://crosscheck-btl.vercel.app">live &#8599;</a>
      <a href="https://github.com/PugarHuda/crosscheck-btl-runtime">github &#8599;</a>
    </div>
  </div>
  <div class=pad>
    <h1 class=heroline>Verify every <em>model</em> answer</h1>
    <p class=sub>Cheap model + strong model, same prompt, in parallel through the BTL gateway. Agree = auto-accept. Disagree = the strong model judges it and flags it. A provider 500s or drops the connection &rarr; fail over.</p>
    <select id=sample></select>
    <textarea id=text placeholder="Paste messy text&hellip;"></textarea>
    <input id=fields placeholder="fields, comma separated &mdash; e.g. vendor, invoice_no, total">
    <div class=row>
      <button id=b-run onclick=run()>Run Crosscheck</button>
      <button class=alt id=b-bench onclick=bench()>Run Benchmark</button>
      <button class=alt id=b-cache onclick=cacheDemo()>&#9889; Demo exact cache</button>
      <span id=status class=mini></span>
    </div>
    <div id=out></div>
    <div id=benchout></div>
    <div id=cacheout></div>
  </div>
</div>
<script>
let SAMPLES=[], LAST=null;
const $=id=>document.getElementById(id);
function setBusy(on,msg){['b-run','b-bench','b-cache'].forEach(i=>$(i).disabled=on);$('status').textContent=on?(msg||'working…'):'';}
function err(e){setBusy(false);$('status').textContent='error: '+e;}
fetch('/api/health').then(r=>r.json()).then(h=>{
  $('dot').className='dot '+(h.ok?'up':'down');
  $('health').title=h.ok?'gateway reachable':'gateway unavailable — demo replays captured results';
}).catch(()=>{$('dot').className='dot down';});
fetch('/api/samples').then(r=>r.json()).then(d=>{SAMPLES=d;
  const s=$('sample');
  s.innerHTML='<option value=-1>— pick a sample or paste your own —</option>'+
    d.map((x,i)=>`<option value=${i}>Sample ${i+1}: ${x.preview}</option>`).join('');
  s.onchange=()=>{const i=+s.value;if(i<0)return;
    $('text').value=SAMPLES[i].text;$('fields').value=SAMPLES[i].fields.join(', ');};
  if(!$('text').value){const i=d.findIndex(x=>x.text.includes('12 bottles'));
    if(i>=0){s.value=i;$('text').value=d[i].text;$('fields').value=d[i].fields.join(', ');}}
});
try{const p=JSON.parse(localStorage.getItem('cc_last')||'null');if(p){$('text').value=p.text||'';$('fields').value=p.fields||'';}}catch(e){}
$('fields').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();run();}});
$('text').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();run();}});
function run(){
  const text=$('text').value;
  const fields=$('fields').value.split(',').map(x=>x.trim()).filter(Boolean);
  if(!text||!fields.length){$('status').textContent='need text + fields';return;}
  try{localStorage.setItem('cc_last',JSON.stringify({text,fields:$('fields').value}));}catch(e){}
  setBusy(true,'calling two providers…');$('out').innerHTML='';
  fetch('/api/extract',{method:'POST',body:JSON.stringify({text,fields})})
   .then(r=>r.json()).then(d=>{setBusy(false);render(d);}).catch(err);
}
function render(d){
  let h='';
  if(d.error){$('out').innerHTML=`<div class="banner warn">gateway error: ${d.error}</div>`;return;}
  LAST=d;
  if(d.replay) h+=`<div class="banner warn">↻ Replay — the gateway was unavailable, so this is a previously captured real result.</div>`;
  if(d.degraded) h+=`<div class="banner warn">⚠ Degraded: both requests served by <b>${d.servedA}</b> — the other provider failed over. Cross-check disabled, all fields flagged.</div>`;
  else if(d.failover) h+=`<div class="banner warn">↺ Failover: a provider errored, so the request was served by ${d.servedA} + ${d.servedB}.</div>`;
  const keys=Object.keys(d.fields), flagged=keys.filter(f=>d.fields[f].needs_review).length;
  h+=`<div class=summary>
    <span><b>${flagged}</b> of ${keys.length} flagged</span>
    <span>· ${d.servedA} + ${d.servedB}</span>
    ${d.ms!=null?`<span>· ${d.ms}ms</span>`:''}
    ${d.cost_usd!=null?`<span>· $${d.cost_usd}</span>`:''}
    <button class=copy onclick=copyJson()>Copy JSON</button>
  </div>`;
  for(const f of keys){const x=d.fields[f];
    h+=`<div class="card ${x.agree?'ok':'flag'}">
      <div class=k>${f}<span class="badge ${x.agree?'b-ok':'b-flag'}">${x.agree?'agreed':'needs review'}</span></div>
      <div class=v>${fmt(x.value)}</div>
      <div class=mini>A(${d.servedA}): ${fmt(x.a)} &nbsp;|&nbsp; B(${d.servedB}): ${fmt(x.b)}</div>
      ${x.reason?`<div class=reason>judge: ${x.reason}</div>`:''}
    </div>`;}
  $('out').innerHTML=h;
}
function copyJson(){
  if(!LAST)return;
  const o={};for(const f in LAST.fields)o[f]=LAST.fields[f].value;
  navigator.clipboard.writeText(JSON.stringify(o,null,2)).then(()=>{
    $('status').textContent='copied ✓';setTimeout(()=>$('status').textContent='',1500);});
}
function fmt(v){return v==null?'<i>null</i>':String(v);}
function cacheDemo(){
  setBusy(true,'firing the same prompt twice…');$('cacheout').innerHTML='';
  fetch('/api/cache-demo').then(r=>r.json()).then(d=>{
    setBusy(false);
    if(d.error){$('cacheout').innerHTML=`<div class="banner warn">${d.error}</div>`;return;}
    $('cacheout').innerHTML=`
    ${d.replay?'<div class="banner warn">↻ Replay — gateway was unavailable; previously captured real timings.</div>':''}
    <div class=grid>
      <div class=stat><b>${d.cold.ms}ms</b><span>1st call · cold (miss)</span></div>
      <div class="stat hl"><b>${d.warm.ms}ms</b><span>2nd call · ${d.cache_hit?'cache HIT ⚡':'warm'}</span></div>
      <div class=stat><b>${d.speedup}×</b><span>faster on hit</span></div>
      <div class=stat><b>$${d.warm.saved.toFixed(6)}</b><span>saved by exact cache</span></div>
    </div>
    <p class=mini>Same prompt, twice, through the gateway (${d.model}). The 2nd call is served from BTL's exact-response cache — faster and cheaper. Real x-btl-saved header, not simulated.</p>`;
  }).catch(err);
}
function bench(){
  setBusy(true,'benchmarking (this hits the API many times)…');$('benchout').innerHTML='';
  fetch('/api/benchmark').then(r=>r.json()).then(m=>{
    setBusy(false);
    if(m.error){$('benchout').innerHTML=`<div class="banner warn">${m.error}</div>`;return;}
    $('benchout').innerHTML=`
    ${m.replay?'<div class="banner warn">↻ Replay — gateway was unavailable; these are previously captured real numbers.</div>':''}
    <div class=grid>
      <div class=stat><b>${m.acc_b}%</b><span>${m.n_fields} fields · Cheap model alone</span></div>
      <div class="stat hl"><b>${m.acc_final}%</b><span>Crosscheck</span></div>
      <div class=stat><b>${m.acc_a}%</b><span>Strong model alone</span></div>
    </div>
    <div class=grid>
      <div class="stat hl"><b>${m.flag_precision}%</b><span>flag precision</span></div>
      <div class=stat><b>${m.review_burden}%</b><span>flagged (judge fired)</span></div>
      <div class=stat><b>${m.catch_rate}%</b><span>of errors flagged</span></div>
      <div class=stat><b>${m.blind_spot_rate}%</b><span>blind spot (shared bias)</span></div>
    </div>
    <div class=grid>
      <div class="stat hl"><b>$${m.cost_usd}</b><span>real gateway charge · this run</span></div>
      <div class=stat><b>$${m.saved_usd}</b><span>saved by exact cache</span></div>
      <div class=stat><b>${m.api_calls}</b><span>API calls (${m.cached_calls} cached)</span></div>
      <div class=stat><b>${m.n_fields}</b><span>fields verified</span></div>
    </div>
    <p class=mini>${m.n_samples} samples. Crosscheck runs BOTH models on every field (it's a verification layer, not a cost saver) — the judge only fires on the ~${m.review_burden}% that disagree. Cost is measured live from the gateway's x-btl-customer-charge header. Blind spot (both models share the bias) is reported, not hidden.</p>`;
  }).catch(err);
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
            try:
                with open(os.path.join(HERE, "samples.json"), encoding="utf-8") as f:
                    data = json.load(f)
                out = [{"text": s["text"], "fields": list(s["fields"].keys()),
                        "preview": s["text"].split("\n")[0][:40]} for s in data]
                return self._send(200, json.dumps(out))
            except (OSError, ValueError) as e:
                return self._send(500, json.dumps({"error": f"samples.json: {e}"}))
        if self.path == "/api/health":
            try:
                cc.list_models()
                return self._send(200, json.dumps({"ok": True}))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "error": str(e)}))
        if self.path == "/api/cache-demo":
            try:
                return self._send(200, json.dumps(cc.cache_demo()))
            except Exception as e:
                if SNAP.get("cache"):
                    return self._send(200, json.dumps({**SNAP["cache"], "replay": True}))
                return self._send(200, json.dumps({"error": str(e)}))
        if self.path == "/api/benchmark":
            try:
                with open(os.path.join(HERE, "samples.json"), encoding="utf-8") as f:
                    samples = json.load(f)
                m = cc.run_benchmark(samples)
                m.pop("rows", None)
                return self._send(200, json.dumps(m))
            except Exception as e:
                if SNAP.get("benchmark"):
                    return self._send(200, json.dumps({**SNAP["benchmark"], "replay": True}))
                return self._send(200, json.dumps({"error": str(e)}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/extract":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, json.dumps({"error": "invalid JSON body"}))
        err = validate_extract(req)
        if err:
            return self._send(400, json.dumps({"error": err}))
        try:
            cc.reset_cost()
            t0 = time.time()
            r = cc.crosscheck(req["text"], req["fields"])
            r["cost_usd"] = round(cc.get_cost()["charge"], 6)
            r["ms"] = round((time.time() - t0) * 1000)
            return self._send(200, json.dumps(r))
        except Exception as e:
            snap = SNAP.get("extract", {}).get(req["text"].strip().lower())
            # only replay if the snapshot actually covers the fields asked for
            if snap and all(f in snap.get("fields", {}) for f in req["fields"]):
                return self._send(200, json.dumps({**snap, "replay": True}))
            return self._send(502, json.dumps({"error": str(e)}))


def _selfcheck():
    assert validate_extract({"text": "hi", "fields": ["a"]}) is None
    assert validate_extract("nope") == "body must be a JSON object"
    assert "text" in validate_extract({"fields": ["a"]})
    assert "text" in validate_extract({"text": "  ", "fields": ["a"]})
    assert "fields" in validate_extract({"text": "hi"})
    assert "fields" in validate_extract({"text": "hi", "fields": []})
    assert "fields" in validate_extract({"text": "hi", "fields": "a"})
    assert "fields" in validate_extract({"text": "hi", "fields": ["a", ""]})
    print("server self-check OK: input validation")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _selfcheck()
        sys.exit(0)
    if not cc.API_KEY:
        print("WARNING: BTL_API_KEY not set — API calls will 401.")
    print(f"Crosscheck dashboard: http://localhost:{PORT}  (Ctrl+C to stop)")
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    # bind localhost only: the dashboard makes API calls on your key — don't
    # expose it to the LAN.
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), H) as srv:
        srv.serve_forever()
