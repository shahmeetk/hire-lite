#!/usr/bin/env python3
"""Build examples/sample_ledger.jsonl from fully synthetic leads by running the real pipeline
(ingest -> validate -> export -> mark-sent -> mark-bounced -> retry) over three fake weeks.

    python3 examples/make_sample_ledger.py [out.jsonl]
"""
import datetime
import json
import pathlib
import random
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hire_lite import config as C  # noqa: E402
from hire_lite import ledger as L  # noqa: E402

COMPANIES = ["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Vandelay", "Stark", "Wayne", "Cyberdyne", "Tyrell",
             "Soylent", "Wonka", "Gringotts", "Oscorp", "Pied Piper", "Massive Dynamic", "Aperture", "Black Mesa",
             "Monarch", "Dunder Mifflin", "Prestige", "Nakatomi", "Virtucon", "Rekall", "Weyland", "Zorg", "Duff",
             "Krusty", "Bluth", "Sterling", "Gekko", "Ollivander", "Spacely", "Cogswell", "Initrode", "Chotchkie"]
ROLES = ["Senior Platform Engineer", "Staff SRE", "DevOps Lead", "Principal Cloud Architect", "Head of Infrastructure",
         "Platform Engineering Manager", "Senior MLOps Engineer", "Cloud Infrastructure Lead", "Director of SRE",
         "Senior DevOps Engineer", "Marketing Manager"]
LOCS = ["Springfield", "Remote", "Remote (worldwide)", "Hybrid, Capital City", "Ogdenville (onsite)",
        "Capital City (onsite)", "Remote, EU time zones", "Shelbyville"]


def main(out: str) -> None:
    rnd = random.Random(7)
    home = pathlib.Path(tempfile.mkdtemp(prefix="hl-sample-"))
    cfg = C.load_config(ROOT / "config.example.yaml", home)
    start = datetime.datetime(2026, 10, 5, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    clock = {"t": start}
    L.now = lambda: clock["t"].isoformat(timespec="seconds")
    n = 0
    for run in range(10):  # Mon/Wed/Fri for three weeks, plus a final Monday
        clock["t"] = start + datetime.timedelta(days=(run // 3) * 7 + (run % 3) * 2)
        harvest = home / f"harvest_{clock['t']:%Y%m%d}.jsonl"
        with open(harvest, "w") as f:
            for _ in range(rnd.randint(7, 11)):
                n += 1
                co = rnd.choice(COMPANIES)
                dom = co.lower().replace(" ", "-") + ".example.com"
                to = rnd.choice(["jobs", "careers", "talent", "hiring"]) + f"@{dom}"
                ev = f"Send your CV to {to}" if rnd.random() > 0.08 else "Apply via our portal."
                f.write(json.dumps(dict(company=co, role=rnd.choice(ROLES), url=f"https://jobs.example.com/{n}",
                                        to=to if rnd.random() > 0.05 else "", location=rnd.choice(LOCS),
                                        posted_date=(clock["t"] - datetime.timedelta(days=rnd.randint(0, 5))).date().isoformat(),
                                        email_source="post body", evidence=ev)) + "\n")
        L.ingest(cfg, str(harvest))
        L.validate(cfg, mx_lookup=lambda d: not d.startswith("zorg"))
        if run in (4, 9):
            continue  # sender laptop offline: validated leads stay queued
        clock["t"] += datetime.timedelta(minutes=30)
        L.export(cfg, 8)
        outbox = [json.loads(x) for x in open(C.path(cfg, "outbox")) if x.strip()]
        res = home / "results.jsonl"
        with open(res, "w") as f:
            for i, lead in enumerate(outbox):
                t = clock["t"] + datetime.timedelta(seconds=20 * i)
                f.write(json.dumps(dict(lead, date=t.isoformat(timespec="seconds"), result="sent")) + "\n")
        L.mark_sent(cfg, [str(res)])
        if outbox and rnd.random() < 0.7:
            clock["t"] += datetime.timedelta(minutes=2)
            victim = rnd.choice(outbox)["to"]
            L.mark_bounced(cfg, [victim])
            bounced = [r for r in L.Ledger(cfg).values() if r["email"] == victim and r["status"] == "bounced"]
            if bounced and rnd.random() < 0.6:
                fixed = "recruiting@" + victim.split("@")[1]
                try:
                    L.retry(cfg, victim, fixed, "careers page footer", evidence=f"Contact: {fixed}")
                except ValueError:
                    pass
    clock["t"] += datetime.timedelta(hours=1)
    sent_retries = [r["email"] for r in L.Ledger(cfg).values() if r["status"] == "sent" and r.get("retry_of")]
    if sent_retries:
        L.mark_bounced(cfg, sent_retries[:1])  # second bounce on the same lead -> dropped
    shutil.copy(C.path(cfg, "ledger"), out)
    shutil.rmtree(home)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "examples" / "sample_ledger.jsonl"))
