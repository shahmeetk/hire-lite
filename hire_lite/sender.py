"""Send the outbox over SMTP using the user's own mailbox. Zero LLM.

Runs on the same machine as the ledger or on a separate laptop: it only needs this
package, ``config.yaml``, the email template, the attachment files and ``outbox.jsonl``.
It writes ``results/results_<ts>.jsonl`` for ``hl mark-sent``.
"""
from __future__ import annotations

import datetime
import json
import mimetypes
import pathlib
import re
import smtplib
import ssl
import string
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Callable, Optional

from . import config as C
from .ledger import now
from .credentials import get_password


def clean_role(role: str) -> str:
    """Drop a trailing location note such as ``(Remote)`` or ``(Hybrid, Springfield)``."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", role or "").strip() or (role or "").strip()


def work_mode(lead: dict, cfg: dict) -> str:
    lane = lead.get("lane", "")
    home = cfg["lanes"][0]["name"] if cfg["lanes"] else ""
    if lane == "remote":
        return "remote"
    if lane == "hybrid":
        return "hybrid"
    if lane and lane == home:
        return f"on-site or hybrid in {cfg['profile'].get('base_location', '')}".strip()
    return lane or "remote or hybrid"


def pick_highlights(role: str, highlights: list, n: int = 3) -> list[str]:
    """Pick up to n fixed highlight lines from config whose ``match`` regex best fits the role."""
    scored = []
    for i, h in enumerate(highlights or []):
        hits = len(re.findall(h.get("match") or "(?!x)x", role or "", re.I))
        scored.append((hits, -i, h.get("text", "")))
    chosen = [t for hits, _, t in sorted(scored, reverse=True) if hits][:n]
    if len(chosen) < n:
        chosen += [h.get("text", "") for h in highlights or [] if h.get("text", "") not in chosen][: n - len(chosen)]
    return [c for c in chosen if c]


def template_vars(lead: dict, cfg: dict) -> dict:
    p = cfg["profile"]
    role = clean_role(lead.get("role", ""))
    company = re.sub(r"\s*\(.*?\)", "", lead.get("company", "")).strip()
    hl = pick_highlights(role, cfg.get("highlights") or [])
    links = [str(x) for x in p.get("links") or []]
    return {
        "company": company, "role": role, "url": lead.get("url", ""), "location": lead.get("location", ""),
        "lane": lead.get("lane", ""), "work_mode": work_mode(lead, cfg),
        "name": p.get("name", ""), "first_name": (p.get("name") or "").split(" ")[0], "email": p.get("email", ""),
        "phone": p.get("phone", ""), "headline": p.get("headline", ""), "base_location": p.get("base_location", ""),
        "notice_period": p.get("notice_period", ""), "links": "\n".join(links), "links_inline": " | ".join(links),
        "highlights": "\n".join(f"- {h}" for h in hl),
        "highlights_html": "".join(f"<li>{_h(h)}</li>" for h in hl),
    }


def _h(s: str) -> str:
    import html

    return html.escape(s or "")


def load_template(path: pathlib.Path) -> tuple[string.Template, string.Template]:
    """Template files start with ``Subject: ...``, a blank line, then the body."""
    text = path.read_text(encoding="utf-8")
    head, _, body = text.partition("\n\n")
    if not head.lower().startswith("subject:"):
        raise ValueError(f"{path}: first line must be 'Subject: ...'")
    return string.Template(head.split(":", 1)[1].strip()), string.Template(body.strip() + "\n")


def build_message(lead: dict, cfg: dict, attachments: list[pathlib.Path]) -> EmailMessage:
    s = cfg["sender"]
    v = template_vars(lead, cfg)
    subj_t, body_t = load_template(C.resolve(cfg, s["template_text"]))
    m = EmailMessage()
    m["From"] = f"{cfg['profile']['name']} <{cfg['profile']['email']}>"
    m["To"] = lead["to"]
    m["Subject"] = subj_t.substitute(v)
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=cfg["profile"]["email"].split("@")[-1] or None)
    m.set_content(body_t.substitute(v))
    if s.get("template_html"):
        html_vars = {k: (_h(x) if not k.endswith("_html") else x) for k, x in v.items()}
        _, html_t = load_template(C.resolve(cfg, s["template_html"]))
        m.add_alternative(html_t.substitute(html_vars), subtype="html")
    for a in attachments:
        ctype = mimetypes.guess_type(a.name)[0] or "application/octet-stream"
        main, sub = ctype.split("/", 1)
        m.add_attachment(a.read_bytes(), maintype=main, subtype=sub, filename=a.name)
    return m


def _register(cfg: dict) -> tuple[pathlib.Path, set[str], int]:
    p = C.path(cfg, "sent_register")
    keys, today = set(), 0
    d = datetime.date.today().isoformat()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            day, _, key = line.partition("\t")
            if key:
                keys.add(key)
                today += day == d
    return p, keys, today


def send(cfg: dict, outbox: Optional[str] = None, max_n: Optional[int] = None, dry_run: bool = False,
         smtp_factory: Optional[Callable[[], smtplib.SMTP]] = None, sleep: Callable[[float], None] = time.sleep) -> dict:
    s, caps = cfg["sender"], cfg["caps"]
    out_p = pathlib.Path(outbox) if outbox else C.path(cfg, "outbox")
    if not out_p.exists() or not out_p.read_text(encoding="utf-8").strip():
        return {"sent": 0, "errors": 0, "skipped": 0, "results": "", "note": "outbox empty"}
    leads = [json.loads(x) for x in out_p.read_text(encoding="utf-8").splitlines() if x.strip()]
    reg_p, sent_keys, sent_today = _register(cfg)
    max_n = caps["send_max_per_run"] if max_n is None else min(max_n, caps["send_max_per_run"])
    budget = max(0, min(max_n, caps["send_daily_max"] - (0 if dry_run else sent_today)))
    attachments = [C.resolve(cfg, a) for a in s.get("attachments") or []]
    missing = [str(a) for a in attachments if not a.exists()]
    if missing and not dry_run:
        raise FileNotFoundError("attachment(s) missing: " + ", ".join(missing))
    attachments = [a for a in attachments if a.exists()]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    res_dir = C.path(cfg, "results_dir")
    res_dir.mkdir(parents=True, exist_ok=True)
    res_p = res_dir / f"results_{ts}.jsonl"
    preview_dir = res_dir / f"preview_{ts}"

    smtp = None
    if not dry_run and leads and budget:
        pw = get_password(cfg)
        if not pw:
            raise RuntimeError(f"no SMTP password: set ${s.get('password_env')} or store it in the OS keychain "
                               f"(service '{s.get('keyring_service')}')")
        if smtp_factory:
            smtp = smtp_factory()
        elif s.get("security") == "ssl":
            smtp = smtplib.SMTP_SSL(s["smtp_host"], int(s["smtp_port"]), context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(s["smtp_host"], int(s["smtp_port"]))
            if s.get("security") == "starttls":
                smtp.starttls(context=ssl.create_default_context())
        smtp.login(s.get("username") or cfg["profile"]["email"], pw)
        pw = None

    counts = {"sent": 0, "errors": 0, "skipped": 0, "dry-run": 0}
    with open(res_p, "w", encoding="utf-8") as log, open(reg_p, "a", encoding="utf-8") as reg:
        for lead in leads:
            key = f"{lead['to'].lower()}|{lead.get('url') or ''}"
            if key in sent_keys:
                counts["skipped"] += 1
                continue
            if counts["sent"] + counts["dry-run"] + counts["errors"] >= budget:
                break
            try:
                msg = build_message(lead, cfg, attachments)
            except Exception as ex:  # template typo, unreadable attachment...
                result = f"error:build:{ex}"
                msg = None
            else:
                if dry_run:
                    preview_dir.mkdir(exist_ok=True)
                    (preview_dir / f"{lead.get('id', 'lead')}.eml").write_bytes(bytes(msg))
                    result = "dry-run"
                else:
                    try:
                        smtp.send_message(msg)
                        result = "sent"
                    except Exception as ex:
                        result = f"error:{ex}"
            if result == "sent":
                reg.write(f"{datetime.date.today().isoformat()}\t{key}\n")
                reg.flush()
                sent_keys.add(key)
            counts["sent" if result == "sent" else "dry-run" if result == "dry-run" else "errors"] += 1
            log.write(json.dumps(dict(date=now(), id=lead.get("id", ""), company=lead.get("company", ""),
                                      role=lead.get("role", ""), url=lead.get("url", ""), to=lead["to"],
                                      result=result, subject=msg["Subject"] if msg else ""), ensure_ascii=False) + "\n")
            if result == "sent" and caps.get("send_delay_seconds"):
                sleep(float(caps["send_delay_seconds"]))
    if smtp:
        smtp.quit()
    counts["results"] = str(res_p)
    if dry_run:
        counts["preview_dir"] = str(preview_dir) if preview_dir.exists() else ""
        counts["missing_attachments"] = missing
    return counts
