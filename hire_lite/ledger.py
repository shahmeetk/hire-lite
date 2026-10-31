"""The ledger: one JSON record per lead, the single source of truth.

Every status change appends to the record's ``history`` so each lead stays traceable
from discovery to send, bounce, retry or skip. No LLM is involved anywhere here.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import os
import pathlib
import re
from typing import Callable, Iterable, Optional

from . import config as C
from . import mx as mxmod

STATUSES = ("new", "skipped", "validated", "retry", "sent", "bounced", "dropped")
# Higher rank wins when the same lead is merged twice.
RANK = {"new": 0, "skipped": 1, "validated": 2, "retry": 3, "sent": 5, "bounced": 6, "dropped": 7}
FIELDS = (
    "id first_seen company role location lane seniority email email_source url posted_date "
    "status reason sent_at batch attempts method evidence retry_of history"
).split()
USED = ("sent", "bounced", "dropped")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
EMAIL_FIND = re.compile(r"[\w.%+\-]+@[\w\-]+(?:\.[\w\-]+)*\.[A-Za-z]{2,}")
OBFUSCATED = [
    (re.compile(r"\s*(?:\[at\]|\(at\)|\{at\}|\sat\s)\s*", re.I), "@"),
    (re.compile(r"\s*(?:\[dot\]|\(dot\)|\{dot\}|\sdot\s)\s*", re.I), "."),
]
SENIORITY = (
    ("head/director", r"head|director|\bvp\b|vice president|chief|\bcto\b|\bavp\b"),
    ("principal/architect", r"principal|staff|architect"),
    ("lead/manager", r"lead|manager"),
    ("senior", r"senior|\bsr\b"),
)


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def rid(email: str, url: str) -> str:
    key = f"{(email or '').strip().lower()}|{(url or '').strip()}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def norm_company(c: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", c or "").strip().lower()


def deobfuscate(text: str) -> str:
    """Turn ``jobs [at] acme [dot] example`` into ``jobs@acme.example`` (only explicit markers)."""
    out = text or ""
    for pat, rep in OBFUSCATED:
        out = pat.sub(rep, out)
    return out


def emails_in(text: str) -> list[str]:
    return EMAIL_FIND.findall(text or "")


def _kw_regex(words: Iterable[str]) -> Optional[re.Pattern]:
    words = [w for w in words if w]
    if not words:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)


def lane_of(text: str, lanes: list[dict], old: str = "") -> str:
    for lane in lanes:
        rx = _kw_regex(lane.get("keywords") or [])
        if rx and rx.search(text or ""):
            return lane["name"]
    names = {lane["name"] for lane in lanes}
    return old if old in names else ""


def seniority_of(role: str) -> str:
    r = (role or "").lower()
    for name, pat in SENIORITY:
        if re.search(pat, r):
            return name
    return "other"


def _event(r: dict, status: str, reason: str, at: Optional[str] = None) -> None:
    r.setdefault("history", []).append({"at": at or now(), "status": status, "reason": reason})


def set_status(r: dict, status: str, reason: str, at: Optional[str] = None) -> None:
    r["status"], r["reason"] = status, reason
    _event(r, status, reason, at)


def make_record(cfg: dict, company: str, role: str, url: str, email: str = "", location: str = "",
                lane: str = "", src: str = "", posted: str = "", status: str = "new", reason: str = "",
                first: Optional[str] = None, method: str = "email", **extra) -> dict:
    first = first or now()
    r = dict(
        id=rid(email, url), first_seen=first, company=(company or "").strip(), role=(role or "").strip(),
        location=(location or "").strip(), lane=lane_of(f"{role} {location} {company}", cfg["lanes"], lane),
        seniority=seniority_of(role), email=(email or "").strip(), email_source=src or "", url=(url or "").strip(),
        posted_date=posted or "", status=status, reason=reason or status, sent_at="", batch="", attempts=0,
        method=method, evidence="", retry_of="", history=[],
    )
    r.update({k: v for k, v in extra.items() if v is not None})
    _event(r, status, r["reason"], first)
    return r


class Ledger:
    """Load/modify/save the JSONL ledger. Writes are atomic (temp file + rename)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.path = C.path(cfg, "ledger")
        self.records: dict[str, dict] = {}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        for k in FIELDS:
                            r.setdefault(k, [] if k == "history" else 0 if k == "attempts" else "")
                        self.records[r["id"]] = r

    def values(self) -> list[dict]:
        return list(self.records.values())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for r in sorted(self.records.values(), key=lambda r: (r["first_seen"], r["id"])):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def merge(self, r: dict) -> bool:
        """Insert or merge a record; returns True if it was new."""
        old = self.records.get(r["id"])
        if not old:
            self.records[r["id"]] = r
            return True
        if RANK[r["status"]] > RANK[old["status"]]:
            for k in ("status", "reason", "sent_at", "batch"):
                old[k] = r[k] or old[k]
            old["history"] = old.get("history", []) + r.get("history", [])
        old["attempts"] = max(old.get("attempts", 0), r.get("attempts", 0))
        old["first_seen"] = min(old["first_seen"], r["first_seen"])
        for k in FIELDS:
            if not old.get(k) and r.get(k):
                old[k] = r[k]
        return False


def bounce_list(cfg: dict) -> set[str]:
    p = C.path(cfg, "bounces")
    if not p.exists():
        return set()
    return {e.lower() for line in p.read_text(encoding="utf-8").splitlines() for e in emails_in(line)}


# ---------------------------------------------------------------- ingest

def ingest(cfg: dict, harvest_file: str) -> dict:
    """Add harvest lines to the ledger. Exact duplicates (same email+url) are ignored."""
    led = Ledger(cfg)
    counts = collections.Counter()
    batch = pathlib.Path(harvest_file).stem
    with open(harvest_file, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                counts["bad-json"] += 1
                continue
            r = make_record(
                cfg, j.get("company"), j.get("role"), j.get("url"), j.get("to") or j.get("email", ""),
                location=j.get("location", ""), lane=j.get("lane", ""),
                src=j.get("email_source") or j.get("source") or "post", posted=j.get("posted_date", ""),
                batch=batch, evidence=j.get("evidence") or j.get("snippet") or "", method=j.get("method", "email"),
            )
            if r["id"] in led.records:
                counts["dup"] += 1
                continue
            prev = _bounced_match(led, r)
            if prev is not None:
                r["retry_of"] = prev["email"]
                set_status(r, "retry", f"corrected address for bounced {prev['email']}")
            led.records[r["id"]] = r
            counts["added"] += 1
    led.save()
    return dict(counts)


def _bounced_match(led: Ledger, r: dict) -> Optional[dict]:
    for o in led.values():
        if o["status"] == "bounced" and norm_company(o["company"]) == norm_company(r["company"]) and (
            (o["url"] and o["url"] == r["url"]) or (o["role"] and o["role"].lower() == r["role"].lower())
        ):
            return o
    return None


# ---------------------------------------------------------------- validate

MxLookup = Callable[[str], Optional[bool]]


def _retry_exhausted(led: Ledger, r: dict) -> bool:
    orig = r.get("retry_of", "").lower()
    for o in led.values():
        if o["id"] == r["id"]:
            continue
        if o["email"].lower() == orig and o.get("retry_of"):
            return True  # the bounced address was itself a retry
        if o.get("retry_of", "").lower() == orig and o["status"] in ("validated", "sent", "bounced", "dropped"):
            return True  # another retry for this bounce already used the one allowed attempt
    return False


def check(cfg: dict, led: Ledger, r: dict, bounces: set[str]) -> str:
    """Return a skip reason, or '' if the lead passes all offline rules (MX is checked separately)."""
    e = r["email"].lower()
    dom = e.split("@")[-1]
    used = [o for o in led.values() if o["status"] in USED and o["id"] != r["id"]]
    is_retry = r["status"] == "retry"
    home = cfg["lanes"][0]["name"] if cfg["lanes"] else ""
    text = f"{r['role']} {r['location']}"
    excl_co = [c.lower() for c in cfg.get("excluded_companies") or []]
    roles = cfg.get("targets", {}).get("roles") or []
    evidence = (r.get("evidence") or "").lower()

    if not EMAIL_RE.match(r["email"]):
        return "bad syntax/no email"
    if e in bounces:
        return "bounce list"
    if dom in {d.lower() for d in cfg.get("free_mail_domains") or []}:
        return "free-mail"
    if evidence and e not in evidence and e not in deobfuscate(evidence):
        return "email not in post text"
    if not evidence and cfg["validate"].get("require_evidence", True) and not is_retry:
        return "no evidence (email must be printed in the post)"
    if any(o["email"].lower() == e for o in used if o["email"]):
        return "dup: address already used"
    if not is_retry and r["url"] and any(o["url"] == r["url"] for o in used):
        return "dup: url already applied"
    if not is_retry and any(
        (norm_company(o["company"]), o["role"].lower()) == (norm_company(r["company"]), r["role"].lower()) for o in used
    ):
        return "dup: same company+role"
    nco = norm_company(r["company"])
    if any(k == nco or k in nco.split() for k in excl_co):
        return "excluded company"
    if roles and not any(re.search(p, r["role"], re.I) for p in roles):
        return "role not targeted"
    excl_loc = _kw_regex(cfg.get("excluded_locations") or [])
    if excl_loc and excl_loc.search(text) and r["lane"] != home:
        return "excluded location"
    if not r["lane"]:
        return "lane unknown/onsite outside home region"
    if is_retry and _retry_exhausted(led, r):
        return "retry exhausted"
    return ""


def validate(cfg: dict, mx_lookup: Optional[MxLookup] = None, skip_mx: bool = False) -> dict:
    led = Ledger(cfg)
    bounces = bounce_list(cfg)
    vcfg = cfg["validate"]
    do_mx = vcfg.get("mx_check", True) and not skip_mx
    cache_p = C.path(cfg, "mx_cache")
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    if mx_lookup is None:
        def mx_lookup(d: str) -> Optional[bool]:
            return mxmod.has_mx(d, vcfg.get("mx_resolver", "https://dns.google/resolve"), vcfg.get("mx_timeout_seconds", 8))
    counts = collections.Counter()
    for r in led.values():
        if r["status"] not in ("new", "retry"):
            continue
        why = check(cfg, led, r, bounces)
        if not why and do_mx:
            dom = r["email"].lower().split("@")[-1]
            if dom not in cache:
                res = mx_lookup(dom)
                if res is not None:
                    cache[dom] = res
            ok = cache.get(dom)
            if ok is None:
                counts["dns-pending"] += 1
                continue
            if not ok:
                why = "no MX"
        if why:
            set_status(r, "skipped", why)
        else:
            set_status(r, "validated", "ok" if r["status"] == "new" else f"retry of {r.get('retry_of')}")
        counts[r["status"]] += 1
    if do_mx:
        cache_p.write_text(json.dumps(cache, indent=0, sort_keys=True))
    led.save()
    return dict(counts)


# ---------------------------------------------------------------- export

def export(cfg: dict, max_n: Optional[int] = None) -> tuple[int, pathlib.Path, str]:
    """Write the next batch of validated leads to outbox.jsonl, ordered by lane priority."""
    led = Ledger(cfg)
    max_n = cfg["caps"]["export_max"] if max_n is None else max_n
    order = {lane["name"]: i for i, lane in enumerate(cfg["lanes"])}
    stamp = re.sub(r"\D", "", now()[:16])
    batch = f"outbox_{stamp[:8]}_{stamp[8:12]}"
    queue = sorted(
        (r for r in led.values() if r["status"] == "validated" and r["email"]),
        key=lambda r: (order.get(r["lane"], len(order)), r["first_seen"]),
    )[:max_n]
    out = C.path(cfg, "outbox")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in queue:
            f.write(json.dumps(dict(id=r["id"], company=r["company"], role=r["role"], url=r["url"], to=r["email"],
                                    location=r["location"], lane=r["lane"]), ensure_ascii=False) + "\n")
            r["batch"] = batch
    led.save()
    return len(queue), out, batch


# ---------------------------------------------------------------- results

SENT_RESULTS = ("sent", "applied")


def mark_sent(cfg: dict, inputs: list[str]) -> tuple[int, int]:
    """Mark leads sent from sender result files (JSONL) and/or bare ids. Returns (marked, send_errors)."""
    led = Ledger(cfg)
    ids: dict[str, str] = {}
    pairs: list[tuple[str, str, str]] = []
    errors = 0
    for x in inputs:
        if os.path.isfile(x):
            for line in open(x, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("{"):
                    j = json.loads(line)
                    res = j.get("result", "sent")
                    if res not in SENT_RESULTS:
                        errors += str(res).startswith("error")
                        continue
                    at = j.get("date") or now()
                    if j.get("id"):
                        ids[j["id"]] = at
                    else:
                        pairs.append(((j.get("to") or "").lower(), j.get("url") or "", at))
                elif re.fullmatch(r"[0-9a-f]{12}", line):
                    ids[line] = now()
        else:
            ids[x] = now()
    done = 0
    for r in led.values():
        at = ids.get(r["id"])
        if at is None:
            at = next((a for e, u, a in pairs if r["email"].lower() == e and (not u or u == r["url"])), None)
        if at is not None and r["status"] in ("validated", "retry", "new"):
            r["sent_at"] = at
            r["attempts"] = r.get("attempts", 0) + 1
            set_status(r, "sent", "sent", at)
            done += 1
    led.save()
    return done, errors


def parse_bounce_lines(text: str) -> dict[str, str]:
    """Parse ``address | reason`` lines (or any text containing addresses) into {address: reason}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        addr_part, _, reason = line.partition(" | ")
        for e in emails_in(addr_part):
            out.setdefault(e.lower(), reason.strip()[:160])
    return out


def mark_bounced(cfg: dict, inputs: list[str]) -> tuple[int, int]:
    """Record bounces from bounce files or bare addresses. Returns (records updated, new bounce-list entries)."""
    found: dict[str, str] = {}
    for x in inputs:
        if os.path.isfile(x):
            for k, v in parse_bounce_lines(open(x, encoding="utf-8").read()).items():
                found.setdefault(k, v)
        else:
            found.setdefault(x.lower(), "")
    known = bounce_list(cfg)
    new = sorted(set(found) - known)
    if new:
        bl = C.path(cfg, "bounces")
        bl.parent.mkdir(parents=True, exist_ok=True)
        with open(bl, "a", encoding="utf-8") as f:
            f.write("".join(e + "\n" for e in new))
    led = Ledger(cfg)
    n = 0
    for r in led.values():
        e = r["email"].lower()
        if e in found and r["status"] in ("sent", "validated", "new", "retry"):
            detail = f" ({found[e]})" if found[e] else ""
            if r.get("retry_of"):
                set_status(r, "dropped", "retry bounced; dropped" + detail)
            else:
                set_status(r, "bounced", "bounced; one retry allowed" + detail)
            n += 1
    led.save()
    return n, len(new)


def retry(cfg: dict, old: str, new: str, where: str, evidence: str = "") -> dict:
    """Queue one corrected address for a bounced lead. A second retry is refused."""
    old = old.lower()
    led = Ledger(cfg)
    src = [r for r in led.values() if r["email"].lower() == old and r["status"] in ("bounced", "dropped")]
    if not src:
        raise ValueError(f"no bounced record for {old}")
    s = src[-1]
    if s["status"] == "dropped" or s.get("retry_of") or any(
        r.get("retry_of", "").lower() == old for r in led.values()
    ):
        raise ValueError(f"retry already used for {old}; lead is dropped")
    if not where:
        raise ValueError("say where the corrected address was published (never guess)")
    r = make_record(cfg, s["company"], s["role"], s["url"], new, location=s["location"], lane=s["lane"],
                    src=where, status="retry", reason=f"corrected address for bounced {old}",
                    retry_of=old, evidence=evidence, batch=s.get("batch", ""))
    if r["id"] in led.records:
        raise ValueError("that address+url is already in the ledger")
    led.records[r["id"]] = r
    led.save()
    return r


# ---------------------------------------------------------------- migrate

def migrate(cfg: dict, legacy: list[str]) -> dict:
    """Upgrade ledger records to the current schema and optionally import legacy send logs.

    Legacy log lines: ``{"date","company","role","url","to","result": applied|sent|skipped|blocked,
    "reason","method"}``.
    """
    led = Ledger(cfg)
    counts = collections.Counter()
    for r in led.values():
        r["lane"] = lane_of(f"{r['role']} {r['location']} {r['company']}", cfg["lanes"], r.get("lane", ""))
        r["seniority"] = seniority_of(r["role"])
        if not r.get("history"):
            _event(r, r["status"], r.get("reason", ""), r.get("sent_at") or r["first_seen"])
        counts["upgraded"] += 1
    for f in legacy:
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            j = json.loads(line)
            st = {"applied": "sent", "sent": "sent", "skipped": "skipped", "blocked": "skipped"}.get(j.get("result"))
            if not st:
                continue
            at = (j.get("date") or now())[:25]
            r = make_record(cfg, j.get("company"), j.get("role"), j.get("url"), j.get("to", ""),
                            location=j.get("location", ""), lane=j.get("lane", ""), src="migrated:" + pathlib.Path(f).name,
                            status=st, reason=(j.get("reason") or j.get("result"))[:160], first=at,
                            method=j.get("method", "email"), batch=pathlib.Path(f).stem)
            if st == "sent":
                r.update(sent_at=at, attempts=1)
            counts["imported" if led.merge(r) else "merged"] += 1
    bl = bounce_list(cfg)
    for r in led.values():
        if r["email"].lower() in bl and r["status"] == "sent":
            set_status(r, "dropped" if r.get("retry_of") else "bounced", "bounced (bounce list)")
            counts["bounced"] += 1
    led.save()
    return dict(counts)
