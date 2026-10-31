"""``hl``: the Hire Lite command line. Every command prints one terse line (``report`` prints <=10)."""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import sys

from . import __version__
from . import config as C
from . import ledger as L
from .report import report_lines, write_dashboard

REPO = pathlib.Path(__file__).resolve().parent.parent


def _fmt(d: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in d.items()) or "nothing to do"


def cmd_init(cfg, a):
    home = pathlib.Path(cfg["_home"])
    made = []
    for src, dst in (("config.example.yaml", "config.yaml"), (".env.example", ".env")):
        s, d = REPO / src, home / dst
        if s.exists() and not d.exists():
            shutil.copy(s, d)
            made.append(dst)
    tpl = home / "templates"
    if not tpl.exists() and (REPO / "templates").exists() and home != REPO:
        shutil.copytree(REPO / "templates", tpl)
        made.append("templates/")
    for key in ("harvest_dir", "results_dir"):
        C.path(cfg, key).mkdir(parents=True, exist_ok=True)
    print("init", " ".join(made) or "nothing new", "-> edit config.yaml and templates/email.txt, add your resume file")


def cmd_doctor(cfg, a):
    p, s = cfg["profile"], cfg["sender"]
    issues = []
    if not cfg["_config_path"]:
        issues.append("no config.yaml (run: hl init)")
    if p["email"].endswith("@example.com") or p["name"] == "Your Name":
        issues.append("profile still has placeholder name/email")
    if not (cfg["lanes"] and cfg["lanes"][0].get("keywords")):
        issues.append("first (home) lane has no keywords")
    for att in s.get("attachments") or []:
        if not C.resolve(cfg, att).exists():
            issues.append(f"attachment missing: {att}")
    if not C.resolve(cfg, s["template_text"]).exists():
        issues.append(f"template missing: {s['template_text']}")
    print("doctor ok" if not issues else "doctor: " + "; ".join(issues))
    return 0 if not issues else 1


def cmd_migrate(cfg, a):
    print("migrate", _fmt(L.migrate(cfg, a.legacy)))


def cmd_ingest(cfg, a):
    print("ingest", _fmt(L.ingest(cfg, a.file)))


def cmd_validate(cfg, a):
    print("validate", _fmt(L.validate(cfg, skip_mx=a.skip_mx)))


def cmd_export(cfg, a):
    n, out, batch = L.export(cfg, a.max)
    print(f"export {n} -> {out} batch {batch}")


def cmd_mark_sent(cfg, a):
    n, errs = L.mark_sent(cfg, a.inputs)
    print(f"mark-sent {n} (send errors {errs})")


def cmd_mark_bounced(cfg, a):
    n, new = L.mark_bounced(cfg, a.inputs)
    print(f"mark-bounced {n} records, +{new} to bounce list")


def cmd_retry(cfg, a):
    try:
        r = L.retry(cfg, a.bounced, a.corrected, a.where, a.evidence or "")
    except ValueError as ex:
        print("retry refused:", ex)
        return 1
    print("retry queued", r["id"], "-> run validate + export")


def cmd_report(cfg, a):
    print("\n".join(report_lines(cfg)))


def cmd_dashboard(cfg, a):
    print("dashboard", write_dashboard(cfg, a.out))


def cmd_send(cfg, a):
    from .sender import send

    r = send(cfg, a.outbox, a.max, dry_run=a.dry_run)
    if r.get("note"):
        print(r["note"])
        return 0
    extra = f" previews {r['preview_dir']}" if r.get("preview_dir") else ""
    miss = f" (missing attachments: {', '.join(r['missing_attachments'])})" if r.get("missing_attachments") else ""
    print(f"send sent={r['sent']} dry-run={r['dry-run']} errors={r['errors']} already-sent={r['skipped']} "
          f"-> {r['results']}{extra}{miss}")
    return 1 if r["errors"] else 0


def cmd_check_bounces(cfg, a):
    from .bounces import check_bounces

    found = check_bounces(cfg, a.since_days)
    lines = [f"{k} | {v}" for k, v in sorted(found.items())]
    out = a.out or str(C.path(cfg, "results_dir") / f"bounces_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("".join(x + "\n" for x in lines), encoding="utf-8")
    print(f"check-bounces {len(found)} addresses -> {out}")


def cmd_discover_hn(cfg, a):
    from .discovery import hn

    ids = a.thread or hn.latest_threads(a.latest)
    leads = hn.harvest(ids, cfg["targets"].get("roles") or [], a.first_line)
    out = a.out or str(C.path(cfg, "harvest_dir") / f"hn_candidates_{datetime.date.today():%Y%m%d}.jsonl")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for lead in leads:
            f.write(json.dumps(lead, ensure_ascii=False) + "\n")
    print(f"discover-hn threads={','.join(map(str, ids)) or '-'} candidates={len(leads)} -> {out} (review before ingest)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hl", description="Hire Lite ledger CLI (zero LLM).")
    p.add_argument("--home", help="working directory holding config.yaml and the ledger (default $HL_HOME or .)")
    p.add_argument("--config", help="config file (default $HL_CONFIG or <home>/config.yaml)")
    p.add_argument("--version", action="version", version=f"hire-lite {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("init", cmd_init, "create config.yaml, .env, harvest/ and results/ in the home dir")
    add("doctor", cmd_doctor, "check config, template and attachments before a real send")
    add("migrate", cmd_migrate, "upgrade ledger schema; optionally import legacy send logs").add_argument("legacy", nargs="*")
    add("ingest", cmd_ingest, "add a harvest JSONL file to the ledger").add_argument("file")
    add("validate", cmd_validate, "apply all rules (syntax, bounces, free-mail, evidence, dedupe, geo, MX)").add_argument(
        "--skip-mx", action="store_true", help="do not query DNS (offline / demo)")
    add("export", cmd_export, "write the next validated batch to outbox.jsonl").add_argument("--max", type=int)
    add("mark-sent", cmd_mark_sent, "mark leads sent from results files or ids").add_argument("inputs", nargs="+")
    add("mark-bounced", cmd_mark_bounced, "record bounces from bounce files or addresses").add_argument("inputs", nargs="+")
    r = add("retry", cmd_retry, "queue ONE corrected address for a bounced lead")
    r.add_argument("bounced")
    r.add_argument("corrected")
    r.add_argument("where", help="where the corrected address is published, e.g. 'careers page footer'")
    r.add_argument("--evidence", help="snippet that contains the corrected address")
    add("report", cmd_report, "print a <=10 line summary")
    add("dashboard", cmd_dashboard, "write a static, self-contained HTML dashboard").add_argument("--out")
    s = add("send", cmd_send, "send outbox.jsonl over SMTP (sender machine)")
    s.add_argument("--outbox")
    s.add_argument("--max", type=int)
    s.add_argument("--dry-run", action="store_true", help="render .eml previews, send nothing")
    b = add("check-bounces", cmd_check_bounces, "scan the mailbox (IMAP, read-only) for bounces")
    b.add_argument("--since-days", type=int)
    b.add_argument("--out")
    h = add("discover-hn", cmd_discover_hn, "HN 'Who is hiring?' candidates with printed emails")
    h.add_argument("--thread", type=int, action="append", help="story id (repeatable); default: latest thread")
    h.add_argument("--latest", type=int, default=1)
    h.add_argument("--first-line", default="", help="regex the comment's first line must match, e.g. 'remote'")
    h.add_argument("--out")
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    cfg = C.load_config(a.config, a.home)
    try:
        return a.fn(cfg, a) or 0
    except (FileNotFoundError, RuntimeError, ValueError) as ex:
        print(f"{a.cmd}: error: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
