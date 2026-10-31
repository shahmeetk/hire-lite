"""Terse text report (<=10 lines, the only thing an agent needs to read) and a static HTML dashboard."""
from __future__ import annotations

import collections
import html
import json
import pathlib

from . import config as C
from .ledger import Ledger, now


def _count(rows, key) -> dict:
    c = collections.Counter((r.get(key) or "-") for r in rows)
    return dict(sorted(c.items(), key=lambda x: (-x[1], x[0])))


def _fmt(d: dict) -> str:
    return " ".join(f"{k}:{v}" for k, v in d.items()) or "-"


def report_lines(cfg: dict) -> list[str]:
    d = Ledger(cfg).values()
    st = _count(d, "status")
    sent = [r for r in d if r["status"] in ("sent", "bounced", "dropped")]
    bounced = st.get("bounced", 0) + st.get("dropped", 0)
    days = collections.Counter(r["sent_at"][:10] for r in sent if r.get("sent_at"))
    last7 = dict(sorted(days.items())[-7:])
    skips = dict(list(_count([r for r in d if r["status"] == "skipped"], "reason").items())[:4])
    return [
        f"leads {len(d)} | emailed {len(sent)} | bounced {bounced} ({100 * bounced // max(1, len(sent))}%) | "
        f"queued {st.get('validated', 0)} | new {st.get('new', 0) + st.get('retry', 0)}",
        "status " + _fmt(st),
        "sent/lane " + _fmt(_count(sent, "lane")),
        "sent/seniority " + _fmt(_count(sent, "seniority")),
        "sent/day " + _fmt(last7),
        "queue/lane " + _fmt(_count([r for r in d if r["status"] == "validated"], "lane")),
        "top skips " + "; ".join(f"{k} ({v})" for k, v in skips.items()) if skips else "top skips -",
    ]


CSS = """
:root{
  --bg:#0b1020; --card:#141a2b; --card2:#1c2438; --line:#2c3854; --fg:#e7edf8; --muted:#93a0b8;
  --accent:#7ee0c6; --blue:#8eb6ff; --amber:#f5c16c; --bad:#ff8b84; --ok:#5ee0a0; --violet:#c7b6ff;
  --shadow:0 18px 50px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{margin:0;color:var(--fg);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
  background:
    radial-gradient(900px 420px at 0% -10%,rgba(142,182,255,.18),transparent 60%),
    radial-gradient(800px 380px at 100% 0%,rgba(126,224,198,.12),transparent 55%),
    var(--bg);}
.wrap{max-width:1240px;margin:0 auto;padding:28px 22px 72px}
.hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;flex-wrap:wrap}
.mark{color:var(--accent);font-size:12px;letter-spacing:.18em;text-transform:uppercase;font-weight:700}
h1{font-size:34px;line-height:1.05;letter-spacing:-.035em;margin:6px 0 8px}
.sub{color:var(--muted);margin:0}
.pill{border:1px solid var(--line);background:rgba(255,255,255,.03);border-radius:999px;padding:6px 10px;color:var(--muted);font-size:12px}
.insights{display:grid;gap:8px;margin:18px 0}
.insight{background:linear-gradient(180deg,rgba(126,224,198,.08),rgba(255,255,255,.02));
  border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:12px;padding:10px 12px}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.kpi,.row,th{font:inherit;color:inherit}
.kpi{text-align:left;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 14px;box-shadow:var(--shadow)}
button.kpi{cursor:pointer}
.kpi b{display:block;font-size:26px;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.kpi span{color:var(--muted);font-size:12px}
.kpi.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset,var(--shadow)}
.pipe{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.pipe button{font:inherit;color:var(--fg);background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:7px 12px;cursor:pointer}
.pipe b{font-variant-numeric:tabular-nums}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 14px;min-width:0}
.card.span2{grid-column:span 2}
.card.span4{grid-column:1 / -1}
.card h3{margin:0 0 10px;font-size:13px;color:var(--muted);font-weight:650}
.row{display:grid;grid-template-columns:minmax(0,14em) minmax(48px,1fr) auto;gap:8px;align-items:center;width:100%;
  background:transparent;border:0;border-radius:8px;padding:3px 4px;cursor:pointer;text-align:left}
.row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .track{display:block;height:8px;border-radius:99px;background:#243049}
.row i{display:block;height:8px;border-radius:99px;background:linear-gradient(90deg,#3d7eff,var(--accent))}
.row b{font-variant-numeric:tabular-nums;min-width:1.5em;text-align:right}
.row.on,.row:hover{background:#243049}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:16px 0 8px}
input,select,button.reset{font:inherit;color:var(--fg);background:#101628;border:1px solid var(--line);border-radius:10px;padding:8px 10px}
input{min-width:min(100%,280px)}
button.reset{cursor:pointer}
#n{color:var(--muted)}
.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:16px;background:rgba(10,14,26,.65);max-height:72vh}
table{border-collapse:collapse;width:100%;font-size:12.5px;table-layout:fixed}
col.c-seen{width:88px} col.c-co{width:92px} col.c-role{width:132px} col.c-loc{width:108px}
col.c-lane{width:64px} col.c-lvl{width:108px} col.c-mail{width:168px} col.c-st{width:86px}
col.c-why{width:128px} col.c-sent{width:108px} col.c-batch{width:118px}
td,th{padding:7px 8px;text-align:left;vertical-align:top;border-bottom:1px solid #223049;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
th{position:sticky;top:0;background:#182033;cursor:pointer;color:var(--muted);font-weight:650;white-space:nowrap}
tr.lead{cursor:pointer} tr.lead:hover td{background:rgba(255,255,255,.03)}
tr.detail td{background:#101628;color:var(--muted);white-space:normal;overflow:visible;text-overflow:clip}
a{color:var(--blue);text-decoration:none}
.tag{display:inline-block;border-radius:999px;padding:1px 8px;font-weight:700;font-size:12px;background:#243049}
.s-sent{color:var(--ok)}.s-validated{color:var(--amber)}.s-bounced,.s-dropped{color:var(--bad)}
.s-skipped{color:var(--muted)}.s-retry{color:var(--violet)}.s-new{color:var(--blue)}
.timeline{list-style:none;margin:8px 0 0;padding:0}
.timeline li{display:grid;grid-template-columns:168px 110px 1fr;gap:8px;padding:4px 0;border-top:1px solid #223049}
.quote{margin:8px 0;padding:8px 10px;border-left:3px solid var(--accent);color:var(--fg)}
.empty{color:var(--muted);padding:8px 0}
@media(max-width:980px){.kpis,.cards{grid-template-columns:1fr 1fr}.card.span2,.card.span4{grid-column:auto}.timeline li{grid-template-columns:1fr}}
@media(max-width:640px){.kpis,.cards{grid-template-columns:1fr}h1{font-size:28px}}
"""

JS = r"""
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mailed=s=>s==='sent'||s==='bounced'||s==='dropped';
let extra={seniority:'',day:'',reason:''}, sortKey='first_seen', sortDir=-1, openId='';
function match(x, skip){
  const q=$('q').value.trim().toLowerCase(), fs=$('fs').value, fl=$('fl').value;
  if(skip!=='status' && fs && x.status!==fs) return false;
  if(skip!=='lane' && fl && (x.lane||'-')!==fl) return false;
  if(skip!=='seniority' && extra.seniority && (x.seniority||'-')!==extra.seniority) return false;
  if(skip!=='day' && extra.day && !(x.sent_at||'').startsWith(extra.day)) return false;
  if(skip!=='reason' && extra.reason && (x.reason||'')!==extra.reason) return false;
  if(q && ![x.company,x.role,x.email,x.reason,x.location,x.status,x.lane].join(' ').toLowerCase().includes(q)) return false;
  return true;
}
const rows=skip=>D.filter(x=>match(x,skip));
function tally(list,key){
  const m={};
  list.forEach(x=>{const k=(key==='day'?(x.sent_at||'').slice(0,10):x[key])||'-'; m[k]=(m[k]||0)+1;});
  return Object.entries(m).sort((a,b)=>b[1]-a[1] || String(a[0]).localeCompare(String(b[0])));
}
function on(dim,k){
  return (dim==='status'&&$('fs').value===k)||(dim==='lane'&&$('fl').value===k)||
    (dim==='seniority'&&extra.seniority===k)||(dim==='day'&&extra.day===k)||(dim==='reason'&&extra.reason===k);
}
function paint(dim,key,list){
  const el=document.querySelector('.bars[data-dim="'+dim+'"]'); if(!el) return;
  const pairs=tally(list,key).slice(0, dim==='reason'?8:12), max=Math.max(1,...pairs.map(p=>p[1]),1);
  el.innerHTML=pairs.map(([k,v])=>'<button type="button" class="row'+(on(dim,k)?' on':'')+'" data-dim="'+dim+'" data-val="'+esc(k)+'">'+
    '<span title="'+esc(k)+'">'+esc(k)+'</span><span class="track"><i style="width:'+Math.max(3,Math.round(100*v/max))+'%"></i></span><b>'+v+'</b></button>'
  ).join('') || '<div class="empty">Nothing in this view</div>';
}
function insights(){
  const n=D.length, sent=D.filter(x=>mailed(x.status)), bounced=D.filter(x=>x.status==='bounced'||x.status==='dropped').length;
  const queued=D.filter(x=>x.status==='validated').length, openB=D.filter(x=>x.status==='bounced').length;
  const rate=sent.length?Math.round(100*bounced/sent.length):0;
  const skips=tally(D.filter(x=>x.status==='skipped'),'reason');
  const lines=[];
  if(!n) lines.push('The ledger is empty. Run ingest on a harvest file, then generate this page again.');
  if(queued) lines.push(queued+' validated lead'+(queued===1?' is':'s are')+' waiting. Send them with scripts/hl_send.sh, or leave them queued if the sender laptop is offline.');
  if(openB) lines.push(openB+' bounced lead'+(openB===1?'':'s')+' can take one corrected address that is printed on the post or the company site. A second bounce drops the lead.');
  if(sent.length && rate>=15) lines.push('Bounce rate is '+rate+'%. Slow down and keep only addresses that appear in the post.');
  if(skips[0]) lines.push('Most common skip: '+skips[0][0]+' ('+skips[0][1]+'). That is the rule rejecting the most leads.');
  if(!lines.length) lines.push('No leads are waiting and nothing bounced. The next run starts with a fresh discovery pass.');
  $('insights').innerHTML=lines.map(t=>'<div class="insight">'+esc(t)+'</div>').join('');
}
function pipe(){
  const steps=[['In ledger',D.length,''],['Ready to send',D.filter(x=>x.status==='validated').length,'validated'],
    ['Emailed',D.filter(x=>mailed(x.status)).length,''],['Retry open',D.filter(x=>x.status==='bounced').length,'bounced'],
    ['Dropped',D.filter(x=>x.status==='dropped').length,'dropped'],['Skipped',D.filter(x=>x.status==='skipped').length,'skipped']];
  $('pipe').innerHTML=steps.map(([name,v,st])=>'<button type="button" data-dim="status" data-val="'+esc(st)+'"'+(st&&$('fs').value===st?' class="on"':'')+'><b>'+v+'</b> '+esc(name)+'</button>').join('');
}
function detail(x){
  const hist=(x.history||[]).map(h=>'<li><time>'+esc(h.at)+'</time><b class="s-'+esc(h.status)+'">'+esc(h.status)+'</b><span>'+esc(h.reason)+'</span></li>').join('');
  const ev=x.evidence?'<div class="quote">'+esc(x.evidence)+'</div>':'<div class="empty">No evidence snippet saved.</div>';
  return '<div><b>'+esc(x.company)+'</b> · '+esc(x.email_source||'source unknown')+
    (x.retry_of?' · retry of '+esc(x.retry_of):'')+' · '+esc(x.attempts||0)+' send'+(x.attempts==1?'':'s')+'</div>'+ev+
    (x.url?'<div><a href="'+esc(x.url)+'" target="_blank" rel="noopener">'+esc(x.url)+'</a></div>':'')+
    '<ol class="timeline">'+hist+'</ol>';
}
function render(){
  insights(); pipe();
  document.querySelectorAll('.kpi').forEach(b=>b.classList.toggle('on', b.dataset.val && b.dataset.val===$('fs').value));
  paint('status','status',rows('status'));
  paint('lane','lane',rows('lane').filter(x=>mailed(x.status)));
  paint('seniority','seniority',rows('seniority').filter(x=>mailed(x.status)));
  paint('day','day',rows('day').filter(x=>mailed(x.status)&&x.sent_at));
  paint('reason','reason',rows('reason').filter(x=>x.status==='skipped'));
  const R=rows('').slice().sort((a,b)=>{
    const av=String(a[sortKey]||''), bv=String(b[sortKey]||'');
    return (av<bv?-1:av>bv?1:0)*sortDir;
  });
  $('n').textContent=R.length+' of '+D.length+' leads';
  document.querySelectorAll('th').forEach(th=>th.textContent=th.dataset.label+(th.dataset.k===sortKey?(sortDir<0?' ↓':' ↑'):''));
  $('t').innerHTML=R.slice(0,3000).map(x=>{
    const role=/^https?:/.test(x.url||'')?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener">'+esc(x.role||'link')+'</a>':esc(x.role);
    const open=openId===x.id;
    return '<tr class="lead" data-id="'+esc(x.id)+'"><td>'+esc((x.first_seen||'').slice(0,10))+'<td>'+esc(x.company)+'<td>'+role+
      '<td>'+esc(x.location)+'<td>'+esc(x.lane)+'<td>'+esc(x.seniority)+'<td>'+esc(x.email)+
      '<td><span class="tag s-'+esc(x.status)+'">'+esc(x.status)+'</span><td>'+esc(x.reason)+
      '<td>'+esc((x.sent_at||'').slice(0,16).replace('T',' '))+'<td>'+esc(x.batch)+'</tr>'+
      (open?'<tr class="detail"><td colspan="11">'+detail(x)+'</td></tr>':'');
  }).join('') || '<tr><td colspan="11" class="empty">No leads match these filters.</td></tr>';
}
function toggle(dim,val){
  if(dim==='status') $('fs').value=$('fs').value===val?'':val;
  else if(dim==='lane') $('fl').value=$('fl').value===val?'':val;
  else extra[dim]=extra[dim]===val?'':val;
  render();
}
document.body.addEventListener('click',e=>{
  const bar=e.target.closest('[data-dim]');
  if(bar){ if(bar.dataset.val) toggle(bar.dataset.dim, bar.dataset.val); return; }
  const th=e.target.closest('th');
  if(th){ sortDir = sortKey===th.dataset.k ? -sortDir : -1; sortKey=th.dataset.k; render(); return; }
  if(e.target.closest('a')) return;
  const tr=e.target.closest('tr.lead');
  if(tr){ openId = openId===tr.dataset.id ? '' : tr.dataset.id; render(); }
});
['q','fs','fl'].forEach(i=>$(i).addEventListener('input',render));
$('clear').addEventListener('click',()=>{$('q').value=$('fs').value=$('fl').value=''; extra={seniority:'',day:'',reason:''}; openId=''; render();});
document.addEventListener('keydown',e=>{
  if(e.key==='/' && document.activeElement!==$('q')){ e.preventDefault(); $('q').focus(); }
  if(e.key==='Escape'){ $('clear').click(); }
});
render();
"""


def render_dashboard(cfg: dict, generated_at: str | None = None) -> str:
    d = Ledger(cfg).values()
    sent = [r for r in d if r["status"] in ("sent", "bounced", "dropped")]
    st = _count(d, "status")
    bounced = st.get("bounced", 0) + st.get("dropped", 0)
    keep = ("id", "first_seen", "company", "role", "location", "lane", "seniority", "email", "url",
            "status", "reason", "sent_at", "batch", "history", "evidence", "email_source", "attempts", "retry_of")
    rows = [{k: r.get(k, "") for k in keep} for r in d]
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    lanes = [lane["name"] for lane in cfg["lanes"]]
    lanes += sorted({r["lane"] for r in d if r["lane"] and r["lane"] not in lanes})
    def kpi(label: str, value, status: str = "") -> str:
        inner = f"<b>{value}</b><span>{html.escape(label)}</span>"
        if not status:
            return f"<div class=kpi>{inner}</div>"
        return f"<button type=button class=kpi data-dim=status data-val=\"{html.escape(status)}\">{inner}</button>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hire Lite dashboard</title><style>{CSS}</style></head><body><div class="wrap">
<header class="hero"><div><div class="mark">Hire Lite</div><h1>Pipeline</h1>
<p class="sub">{len(d)} leads in the ledger · generated {html.escape(generated_at or now())} · this file stays on your machine</p></div>
<div class="pill">Click any number to filter · click a row for its history · / to search</div></header>
<section id="insights" class="insights"></section>
<section class="kpis">{kpi('leads', len(d))}{kpi('emailed', len(sent), '')}{kpi('bounced or dropped', bounced)}
{kpi('bounce rate', f"{100 * bounced // max(1, len(sent))}%")}{kpi('queued to send', st.get('validated', 0), 'validated')}
{kpi('skipped', st.get('skipped', 0), 'skipped')}</section>
<section id="pipe" class="pipe" aria-label="Pipeline"></section>
<section class="cards">
<div class="card"><h3>Status (all leads)</h3><div class="bars" data-dim="status"></div></div>
<div class="card"><h3>Emailed by lane</h3><div class="bars" data-dim="lane"></div></div>
<div class="card"><h3>Emailed by seniority</h3><div class="bars" data-dim="seniority"></div></div>
<div class="card"><h3>Emailed by day</h3><div class="bars" data-dim="day"></div></div>
<div class="card span4"><h3>Top skip reasons</h3><div class="bars" data-dim="reason"></div></div>
</section>
<div class="controls"><input id=q placeholder="Search company, role, email, or reason" aria-label="Search">
<select id=fs aria-label="Status"><option value="">any status</option>{''.join(f'<option>{html.escape(k)}</option>' for k in st)}</select>
<select id=fl aria-label="Lane"><option value="">any lane</option>{''.join(f'<option>{html.escape(k)}</option>' for k in lanes)}<option value="-">none</option></select>
<button type=button class=reset id=clear>Clear</button><span id=n></span></div>
<div class="tablewrap"><table><colgroup><col class=c-seen><col class=c-co><col class=c-role><col class=c-loc><col class=c-lane><col class=c-lvl><col class=c-mail><col class=c-st><col class=c-why><col class=c-sent><col class=c-batch></colgroup><thead><tr>
<th data-k="first_seen" data-label="first seen">first seen<th data-k="company" data-label="company">company
<th data-k="role" data-label="role">role<th data-k="location" data-label="location">location
<th data-k="lane" data-label="lane">lane<th data-k="seniority" data-label="level">level
<th data-k="email" data-label="email">email<th data-k="status" data-label="status">status
<th data-k="reason" data-label="reason">reason<th data-k="sent_at" data-label="sent">sent
<th data-k="batch" data-label="batch">batch</tr></thead><tbody id=t></tbody></table></div>
</div>
<script>const D={data};
{JS}</script></body></html>
"""


def write_dashboard(cfg: dict, out: str | None = None) -> pathlib.Path:
    p = pathlib.Path(out) if out else C.path(cfg, "dashboard")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_dashboard(cfg), encoding="utf-8")
    return p
