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
:root{--fg:#1f2328;--muted:#57606a;--line:#d0d7de;--bg:#f6f8fa;--accent:#2f81f7}
*{box-sizing:border-box}body{font:13px/1.45 system-ui,-apple-system,Segoe UI,Arial,sans-serif;margin:20px;color:var(--fg)}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 16px}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px}.kpi{border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:120px}
.kpi b{display:block;font-size:22px}.kpi span{color:var(--muted)}
.cards{display:flex;flex-wrap:wrap;gap:12px}.card{border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:320px;flex:1}
.card h3{margin:0 0 8px;font-size:13px}.row{display:flex;align-items:center;gap:8px;margin:4px 0}
.row span{width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bar{height:12px;background:var(--accent);border-radius:3px}
.controls{margin:16px 0 8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}input,select{padding:5px 7px;border:1px solid var(--line);border-radius:6px;font:inherit}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #eaeef2;padding:5px 6px;text-align:left;vertical-align:top}
th{background:var(--bg);position:sticky;top:0}td:nth-child(1),td:nth-child(10){white-space:nowrap}a{color:#0969da;text-decoration:none}
.s-sent{color:#1a7f37;font-weight:600}.s-bounced,.s-dropped{color:#cf222e;font-weight:600}.s-skipped{color:#8c959f}
.s-validated{color:#9a6700;font-weight:600}.s-retry{color:#8250df;font-weight:600}.s-new{color:#0969da}
"""

JS = """
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){
  const q=$('q').value.toLowerCase(),fs=$('fs').value,fl=$('fl').value;
  const R=D.filter(x=>(!fs||x.status==fs)&&(!fl||(x.lane||'-')==fl)&&
    (!q||[x.company,x.role,x.email,x.reason,x.location].join(' ').toLowerCase().includes(q))).reverse();
  $('n').textContent=R.length+' rows';
  $('t').innerHTML=R.slice(0,3000).map(x=>{
    const role=/^https?:/.test(x.url||'')?`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.role||'link')}</a>`:esc(x.role);
    const hist=(x.history||[]).map(h=>`${h.at} ${h.status}: ${h.reason}`).join('\\n');
    return `<tr title="${esc(hist)}"><td>${esc((x.first_seen||'').slice(0,10))}<td>${esc(x.company)}<td>${role}<td>${esc(x.location)}`+
      `<td>${esc(x.lane)}<td>${esc(x.seniority)}<td>${esc(x.email)}<td class="s-${esc(x.status)}">${esc(x.status)}`+
      `<td>${esc(x.reason)}<td>${esc((x.sent_at||'').slice(0,16).replace('T',' '))}<td>${esc(x.batch)}</tr>`}).join('');
}
['q','fs','fl'].forEach(i=>$(i).addEventListener('input',render));render();
"""


def _bars(title: str, counts: dict) -> str:
    m = max(counts.values() or [1])
    rows = "".join(
        f"<div class=row><span title='{html.escape(str(k))}'>{html.escape(str(k))}</span>"
        f"<div class=bar style='width:{max(2, int(260 * v / m))}px'></div><b>{v}</b></div>"
        for k, v in counts.items()
    ) or "<div class=row><span>none yet</span></div>"
    return f"<div class=card><h3>{html.escape(title)}</h3>{rows}</div>"


def render_dashboard(cfg: dict, generated_at: str | None = None) -> str:
    d = Ledger(cfg).values()
    sent = [r for r in d if r["status"] in ("sent", "bounced", "dropped")]
    st = _count(d, "status")
    bounced = st.get("bounced", 0) + st.get("dropped", 0)
    days = dict(sorted(collections.Counter(r["sent_at"][:10] for r in sent if r.get("sent_at")).items()))
    skips = dict(list(_count([r for r in d if r["status"] == "skipped"], "reason").items())[:8])
    keep = ("id", "first_seen", "company", "role", "location", "lane", "seniority", "email", "url",
            "status", "reason", "sent_at", "batch", "history")
    rows = [{k: r.get(k, "") for k in keep} for r in d]
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    lanes = [lane["name"] for lane in cfg["lanes"]]
    lanes += sorted({r["lane"] for r in d if r["lane"] and r["lane"] not in lanes})
    kpi = lambda label, v: f"<div class=kpi><b>{v}</b><span>{label}</span></div>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hire Lite dashboard</title><style>{CSS}</style></head><body>
<h1>Hire Lite dashboard</h1>
<p class=sub>{len(d)} leads in ledger &middot; generated {html.escape(generated_at or now())} &middot; static file, no network</p>
<div class=kpis>{kpi('leads', len(d))}{kpi('emailed', len(sent))}{kpi('bounced/dropped', bounced)}
{kpi('bounce rate', f"{100 * bounced // max(1, len(sent))}%")}{kpi('queued', st.get('validated', 0))}{kpi('skipped', st.get('skipped', 0))}</div>
<div class=cards>{_bars('Status (all leads)', st)}{_bars('Emailed by lane', _count(sent, 'lane'))}
{_bars('Emailed by seniority', _count(sent, 'seniority'))}{_bars('Emailed by day', days)}{_bars('Top skip reasons', skips)}</div>
<div class=controls><input id=q placeholder="search company / role / email / reason" size=40>
<select id=fs><option value="">any status</option>{''.join(f'<option>{html.escape(k)}</option>' for k in st)}</select>
<select id=fl><option value="">any lane</option>{''.join(f'<option>{html.escape(k)}</option>' for k in lanes)}<option value="-">none</option></select>
<span id=n></span></div>
<table><thead><tr><th>first seen<th>company<th>role<th>location<th>lane<th>level<th>email<th>status<th>reason<th>sent<th>batch</tr></thead>
<tbody id=t></tbody></table>
<script>const D={data};{JS}</script></body></html>
"""


def write_dashboard(cfg: dict, out: str | None = None) -> pathlib.Path:
    p = pathlib.Path(out) if out else C.path(cfg, "dashboard")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_dashboard(cfg), encoding="utf-8")
    return p
