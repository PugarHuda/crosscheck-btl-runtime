"""Thin dashboard for Crosscheck. Pure stdlib http.server, no framework.

    set BTL_API_KEY=...    (PowerShell: $env:BTL_API_KEY="...")
    python server.py       -> http://localhost:8000
"""
import os, sys, json, http.server, socketserver
import crosscheck as cc

# request logic lives in crosscheck.py (shared with the Vercel serverless functions)
validate_extract = cc.validate_extract

PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(__file__)

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Crosscheck · BTL Runtime</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light;
  --ink:#0a0f1e;--paper:#ffffff;--wash:#f4f6f9;--line:#e2e6ee;--line2:#cfd6e2;
  --text:#0f1622;--muted:#5c6675;--accent:#1f5fff;--good:#12894e;--flag:#d5382e;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  --serif:Georgia,"Times New Roman",serif}
*{box-sizing:border-box}
body{font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--ink);
  color:var(--text);margin:0;padding:clamp(6px,1.4vw,14px)}
.frame{max-width:960px;margin:0 auto;background:var(--paper);border:1px solid var(--ink);border-radius:4px;overflow:hidden}
.pad{padding:clamp(18px,3vw,30px)}
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;
  padding:14px clamp(18px,3vw,26px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:-.01em;font-size:17px}
.mark{width:22px;height:22px;flex:none;color:var(--ink)}
.toplinks{display:flex;align-items:center;gap:16px;font-family:var(--mono);font-size:12px;color:var(--muted)}
.toplinks a{color:var(--muted);text-decoration:none} .toplinks a:hover{color:var(--text)}
.dot{width:8px;height:8px;border-radius:50%;background:#b6bdc9;display:inline-block;margin-right:6px;vertical-align:middle}
.dot.up{background:var(--good);box-shadow:0 0 0 3px color-mix(in srgb,var(--good) 20%,transparent)}
.dot.down{background:var(--flag);box-shadow:0 0 0 3px color-mix(in srgb,var(--flag) 20%,transparent)}
.heroline{font-family:var(--mono);text-transform:uppercase;font-size:clamp(19px,3vw,27px);
  letter-spacing:-.01em;margin:0 0 6px;font-weight:600}
.heroline em{font-family:var(--serif);font-style:italic;text-transform:none;font-weight:500;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 20px;font-size:13.5px;max-width:70ch}
textarea,select,#fields{width:100%;background:#fff;color:var(--text);border:1px solid var(--line2);
  border-radius:8px;padding:10px;font:inherit;margin-top:8px}
textarea:focus-visible,select:focus-visible,#fields:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);border-color:var(--accent)}
textarea{height:110px;resize:vertical;font-family:var(--mono);font-size:13px}
#fields{font-family:var(--mono);font-size:13px}
select{font-family:var(--mono);font-size:12.5px}
button{background:var(--ink);color:#fff;border:0;border-radius:8px;padding:10px 17px;
  font-family:var(--mono);font-size:12.5px;font-weight:600;cursor:pointer;margin:12px 8px 0 0}
button.alt{background:#fff;border:1px solid var(--ink);color:var(--text)}
button:hover{filter:brightness(1.08)} button.alt:hover{background:var(--wash)}
button:disabled{opacity:.45;cursor:progress;filter:none}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.modelrow{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px}
.modelrow label{flex:1;min-width:168px;font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--muted);display:flex;flex-direction:column;gap:5px}
.modelrow select{margin-top:0}
.batchbox{margin-top:18px;border:1px solid var(--line);border-radius:8px;background:var(--wash)}
.batchbox>summary{font-family:var(--mono);font-size:12px;cursor:pointer;color:var(--muted);padding:12px 14px;list-style:none}
.batchbox>summary::-webkit-details-marker{display:none}
.batchbox>summary::before{content:"\25B8 ";color:var(--accent)}
.batchbox[open]>summary::before{content:"\25BE "}
.batchbody{padding:0 14px 14px}
#batchInput{height:86px}
.scroll{overflow-x:auto;margin-top:10px}
.btable{border-collapse:collapse;font-size:12px;font-family:var(--mono);min-width:100%}
.btable th,.btable td{border:1px solid var(--line);padding:6px 9px;text-align:left;white-space:nowrap}
.btable th{background:#fff;color:var(--muted);text-transform:uppercase;font-size:10px;letter-spacing:.05em}
.btable td.f{background:color-mix(in srgb,var(--flag) 12%,transparent);color:var(--flag);font-weight:600}
.summary{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;
  color:var(--muted);margin:16px 0 6px}
.summary b{color:var(--text)}
.summary .copy{margin-left:auto;background:#fff;border:1px solid var(--line2);color:var(--text);
  border-radius:6px;padding:5px 11px;font-family:var(--mono);font-size:11px;cursor:pointer}
.summary .copy:hover{border-color:var(--accent)}
.card{border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:11px 14px;margin:9px 0;background:var(--wash)}
.ok{border-left-color:var(--good)} .flag{border-left-color:var(--flag)}
.k{font-weight:600;font-family:var(--mono);font-size:13px}
.v{font-size:18px;margin:3px 0;font-family:var(--mono);font-variant-numeric:tabular-nums}
.mini{color:var(--muted);font-size:12px;font-family:var(--mono)}
.badge{font-size:10px;padding:2px 8px;border-radius:20px;margin-left:8px;font-family:var(--mono);letter-spacing:.04em;text-transform:uppercase}
.b-ok{background:color-mix(in srgb,var(--good) 13%,transparent);color:var(--good)}
.b-flag{background:color-mix(in srgb,var(--flag) 13%,transparent);color:var(--flag)}
.banner{padding:10px 14px;border-radius:8px;margin:10px 0;font-size:13px;font-family:var(--mono)}
.warn{background:#fff7e6;border:1px solid #e7b955;color:#7a5310}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.stat{background:var(--wash);border:1px solid var(--line);border-radius:10px;padding:14px;text-align:center}
.stat b{font-size:25px;display:block;font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--text)}
.stat span{font-size:11px;color:var(--muted);font-family:var(--mono)}
.hl{background:#fff;border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
.hl b{color:var(--accent)}
.reason{color:var(--muted);font-size:12px;margin-top:4px;font-style:italic}
</style>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%231f5fff'%3E%3Crect x='2' y='2' width='6' height='6'/%3E%3Crect x='16' y='2' width='6' height='6'/%3E%3Crect x='9' y='9' width='6' height='6'/%3E%3Crect x='2' y='16' width='6' height='6'/%3E%3Crect x='16' y='16' width='6' height='6'/%3E%3C/svg%3E">
</head><body>
<div class=frame>
  <div class=top>
    <div class=brand>
      <svg class=mark viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x=2 y=2 width=6 height=6 /><rect x=16 y=2 width=6 height=6 /><rect x=9 y=9 width=6 height=6 /><rect x=2 y=16 width=6 height=6 /><rect x=16 y=16 width=6 height=6 /></svg>
      crosscheck.
    </div>
    <div class=toplinks>
      <span id=health title="checking gateway…" aria-label="gateway status"><span class=dot id=dot aria-hidden=true></span>gateway</span>
      <a href="/">&#8592; landing</a>
      <a href="https://github.com/PugarHuda/crosscheck-btl-runtime">github &#8599;</a>
    </div>
  </div>
  <div class=pad>
    <h1 class=heroline>Verify every <em>model</em> answer</h1>
    <p class=sub>Cheap model + strong model, same prompt, in parallel through the BTL gateway. Agree = auto-accept. Disagree = the strong model judges it and flags it. A provider 500s or drops the connection &rarr; fail over.</p>
    <select id=sample aria-label="Choose a sample document"></select>
    <textarea id=text aria-label="Text to extract fields from" placeholder="Paste messy text&hellip;"></textarea>
    <input id=fields aria-label="Fields to extract, comma separated" placeholder="fields, comma separated &mdash; e.g. vendor, invoice_no, total">
    <div class=row>
      <button class=alt id=b-suggest onclick=suggestFields()>&#10024; Suggest fields</button>
      <span class=mini>let a model propose fields from the text above</span>
    </div>
    <div class=modelrow>
      <label>Model A (reference) <select id=modelA aria-label="Model A"></select></label>
      <label>Model B (cross-check) <select id=modelB aria-label="Model B"></select></label>
      <label>Model C (optional &mdash; majority vote) <select id=modelC aria-label="Model C (optional)"></select></label>
    </div>
    <div class=row>
      <button id=b-run onclick=run()>Run Crosscheck</button>
      <button class=alt id=b-compare onclick=runCompare()>Compare models</button>
      <button class=alt id=b-bench onclick=bench()>Run Benchmark</button>
      <button class=alt id=b-cache onclick=cacheDemo()>&#9889; Demo exact cache</button>
      <span id=status class=mini role=status aria-live=polite></span>
    </div>
    <div id=out></div>
    <div id=benchout></div>
    <div id=cacheout></div>
    <details class=batchbox>
      <summary>Batch mode &mdash; verify many records at once (JSONL, one per line)</summary>
      <div class=batchbody>
        <textarea id=batchInput aria-label="Batch JSONL input"></textarea>
        <div class=row><button class=alt id=b-batch onclick=runBatch()>Run batch</button></div>
        <div id=batchout></div>
      </div>
    </details>
  </div>
</div>
<script>
let SAMPLES=[], LAST=null;
const $=id=>document.getElementById(id);
function setBusy(on,msg){['b-run','b-compare','b-bench','b-cache'].forEach(i=>$(i).disabled=on);$('status').textContent=on?(msg||'working…'):'';}
function err(e){setBusy(false);$('status').textContent='error: '+e;}
fetch('/api/health').then(r=>r.json()).then(h=>{
  $('dot').className='dot '+(h.ok?'up':'down');
  $('health').title=h.ok?'gateway reachable':'gateway unavailable — demo replays captured results';
}).catch(()=>{$('dot').className='dot down';});
fetch('/api/models').then(r=>r.json()).then(d=>{
  $('modelA').innerHTML=d.models.map(m=>`<option ${m===d.default_a?'selected':''}>${m}</option>`).join('');
  $('modelB').innerHTML=d.models.map(m=>`<option ${m===d.default_b?'selected':''}>${m}</option>`).join('');
  $('modelC').innerHTML='<option value="">— none —</option>'+d.models.map(m=>`<option>${m}</option>`).join('');
}).catch(()=>{});
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
$('batchInput').value=[
 '{"text":"Invoice AC-12 \\u2014 subtotal 200, tax 20, total 220, net 30","fields":["invoice_no","total","terms"]}',
 '{"text":"Order: 4 boxes of 6 units each","fields":["total_units"]}',
 '{"text":"Ticket TK-88 priority Low, due in 24h","fields":["ticket_no","priority"]}'
].join('\\n');
$('fields').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();run();}});
$('text').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();run();}});
function run(){
  const text=$('text').value;
  const fields=$('fields').value.split(',').map(x=>x.trim()).filter(Boolean);
  if(!text||!fields.length){$('status').textContent='need text + fields';return;}
  try{localStorage.setItem('cc_last',JSON.stringify({text,fields:$('fields').value}));}catch(e){}
  const mA=$('modelA').value, mB=$('modelB').value, mC=$('modelC').value;
  $('out').innerHTML='';
  if(mC){
    const models=[mA,mB,mC].filter(Boolean);
    setBusy(true,'polling '+models.length+' providers…');
    fetch('/api/consensus',{method:'POST',body:JSON.stringify({text,fields,models})})
     .then(r=>r.json()).then(d=>{setBusy(false);renderConsensus(d);}).catch(err);
    return;
  }
  const body={text,fields}; if(mA&&mB) body.models=[mA,mB];
  setBusy(true,'calling two providers…');
  fetch('/api/extract',{method:'POST',body:JSON.stringify(body)})
   .then(r=>r.json()).then(d=>{setBusy(false);render(d);}).catch(err);
}
function renderConsensus(d){
  if(d.error){$('out').innerHTML=`<div class="banner warn">gateway error: ${d.error}</div>`;return;}
  LAST=d;
  const keys=Object.keys(d.fields), flagged=keys.filter(f=>d.fields[f].needs_review).length;
  let h=`<div class=summary>
    <span><b>${flagged}</b> of ${keys.length} flagged</span>
    <span>· ${d.models.join(' + ')}</span>
    ${d.ms!=null?`<span>· ${d.ms}ms</span>`:''}${d.cost_usd!=null?`<span>· $${d.cost_usd}</span>`:''}
    <button class=copy onclick=copyJson()>Copy JSON</button></div>`;
  for(const f of keys){const x=d.fields[f];const ok=x.agreement==='unanimous';
    const votes=Object.entries(x.votes).map(([m,v])=>`${m}: <b>${fmt(v)}</b>`).join(' &nbsp;·&nbsp; ');
    h+=`<div class="card ${ok?'ok':'flag'}">
      <div class=k>${f}<span class="badge ${ok?'b-ok':'b-flag'}">${x.agreement}</span></div>
      <div class=v>${fmt(x.value)}</div>
      <div class=mini>${votes}</div>
    </div>`;}
  $('out').innerHTML=h;
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
    <p class=mini>${m.n_samples} samples${m.partial?' · partial live subset — full 23-sample run is local (python crosscheck.py bench)':''}. Crosscheck runs BOTH models on every field (it's a verification layer, not a cost saver) — the judge only fires on the ~${m.review_burden}% that disagree. Cost is measured live from the gateway's x-btl-customer-charge header. Blind spot (both models share the bias) is reported, not hidden.</p>`;
  }).catch(err);
}
function runBatch(){
  const lines=$('batchInput').value.split('\\n').map(l=>l.trim()).filter(Boolean);
  let records; try{records=lines.map(l=>JSON.parse(l));}catch(e){$('batchout').innerHTML=`<div class="banner warn">bad JSONL line: ${e}</div>`;return;}
  const mA=$('modelA').value,mB=$('modelB').value,body={records}; if(mA&&mB)body.models=[mA,mB];
  const btn=$('b-batch');btn.disabled=true;$('batchout').innerHTML='<p class=mini>verifying '+records.length+' records…</p>';
  fetch('/api/batch',{method:'POST',body:JSON.stringify(body)}).then(r=>r.json()).then(d=>{
    btn.disabled=false;
    if(d.error){$('batchout').innerHTML=`<div class="banner warn">${d.error}</div>`;return;}
    renderBatch(d);
  }).catch(e=>{btn.disabled=false;$('batchout').innerHTML=`<div class="banner warn">${e}</div>`;});
}
function renderBatch(d){
  const cols=[...new Set(d.results.flatMap(r=>r.fields?Object.keys(r.fields):[]))];
  let h=`<p class=mini>${d.results.length} records &middot; ${d.ms}ms &middot; $${d.cost_usd} &middot; flagged cells in red</p>
    <div class=scroll><table class=btable><tr><th>#</th>${cols.map(c=>`<th>${c}</th>`).join('')}</tr>`;
  d.results.forEach((r,i)=>{
    if(r.error){h+=`<tr><td>${i+1}</td><td class=f colspan=${cols.length}>error: ${r.error}</td></tr>`;return;}
    const flg=new Set(r.flagged||[]);
    h+=`<tr><td>${i+1}</td>${cols.map(c=>{const v=r.fields[c];return `<td class="${flg.has(c)?'f':''}">${v==null?'':String(v)}</td>`;}).join('')}</tr>`;
  });
  h+='</table></div>';
  $('batchout').innerHTML=h;
}
function runCompare(){
  const text=$('text').value, fields=$('fields').value.split(',').map(x=>x.trim()).filter(Boolean);
  if(!text||!fields.length){$('status').textContent='need text + fields';return;}
  const models=[$('modelA').value,$('modelB').value,$('modelC').value].filter(Boolean);
  setBusy(true,'comparing '+models.length+' providers…');$('out').innerHTML='';
  fetch('/api/compare',{method:'POST',body:JSON.stringify({text,fields,models})})
   .then(r=>r.json()).then(d=>{setBusy(false);renderCompare(d);}).catch(err);
}
function renderCompare(d){
  if(d.error){$('out').innerHTML=`<div class="banner warn">${d.error}</div>`;return;}
  const ok=d.rows.filter(r=>r.values);
  const minMs=ok.length?Math.min(...ok.map(r=>r.ms)):0, minCost=ok.length?Math.min(...ok.map(r=>r.cost)):0;
  let h=`<p class=mini>compared ${d.models.length} providers &middot; fastest &amp; cheapest &#9733; &middot; disagreeing fields in red</p>
    <div class=scroll><table class=btable><tr><th>provider</th><th>latency</th><th>cost</th>${d.fields.map(f=>`<th class="${d.agree[f]?'':'f'}">${f}</th>`).join('')}</tr>`;
  d.rows.forEach(r=>{
    if(r.error){h+=`<tr><td>${r.model}</td><td class=f colspan=${d.fields.length+2}>error: ${r.error}</td></tr>`;return;}
    h+=`<tr><td>${r.served}</td><td>${r.ms}ms${r.ms===minMs?' &#9733;':''}</td><td>$${r.cost}${r.cost===minCost?' &#9733;':''}</td>${d.fields.map(f=>`<td class="${d.agree[f]?'':'f'}">${r.values[f]==null?'':String(r.values[f])}</td>`).join('')}</tr>`;
  });
  h+='</table></div>';
  $('out').innerHTML=h;
}
function suggestFields(){
  const text=$('text').value; if(!text){$('status').textContent='paste text first';return;}
  const btn=$('b-suggest'); btn.disabled=true; $('status').textContent='suggesting fields…';
  fetch('/api/suggest',{method:'POST',body:JSON.stringify({text})}).then(r=>r.json()).then(d=>{
    btn.disabled=false; $('status').textContent='';
    if(d.error){$('status').textContent='error: '+d.error;return;}
    $('fields').value=(d.fields||[]).join(', ');
    $('status').textContent='suggested '+(d.fields||[]).length+' fields ✓';setTimeout(()=>$('status').textContent='',1800);
  }).catch(e=>{btn.disabled=false;$('status').textContent='error: '+e;});
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
                return self._send(200, json.dumps(cc.api_samples()))
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}))
        if self.path == "/api/health":
            return self._send(200, json.dumps(cc.api_health()))
        if self.path == "/api/models":
            return self._send(200, json.dumps(cc.api_models()))
        if self.path == "/api/cache-demo":
            return self._send(200, json.dumps(cc.api_cache()))
        if self.path == "/api/benchmark":
            try:
                return self._send(200, json.dumps(cc.api_benchmark()))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        return self._send(404, json.dumps({"error": "not found"}))

    POST_ROUTES = {"/api/extract": "api_extract", "/api/consensus": "api_consensus",
                   "/api/batch": "api_batch", "/api/compare": "api_compare",
                   "/api/suggest": "api_suggest"}

    def do_POST(self):
        fn = self.POST_ROUTES.get(self.path)
        if not fn:
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, json.dumps({"error": "invalid JSON body"}))
        code, obj = getattr(cc, fn)(req)
        return self._send(code, json.dumps(obj))


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
