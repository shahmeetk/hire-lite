"""Hacker News "Who is hiring?" helper.

Uses the public HN Firebase API and the Algolia HN search API (no scraping, no login).
Keeps only comments that print a contact email and match your target roles, and
emits harvest-format JSONL lines with the email snippet as ``evidence``. Review the
output before ingesting: it is a candidate list, not a send list.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime
import html
import json
import re
import urllib.request
from typing import Iterable, Optional

from ..ledger import deobfuscate, emails_in

ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
ALGOLIA = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=20"
UA = {"User-Agent": "hire-lite/0.1 (+https://github.com/shahmeetk/hire-lite)"}


def _get(url: str, timeout: float = 20) -> Optional[dict]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def latest_threads(n: int = 1) -> list[int]:
    data = _get(ALGOLIA) or {}
    hits = [h for h in data.get("hits", []) if "who is hiring" in (h.get("title") or "").lower()]
    return [int(h["objectID"]) for h in hits[:n]]


def to_text(comment_html: str) -> str:
    t = comment_html.replace("<p>", "\n")
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


def parse_comment(c: dict, role_rx: Optional[re.Pattern], first_line_rx: Optional[re.Pattern]) -> Optional[dict]:
    if not c or c.get("dead") or c.get("deleted") or "text" not in c:
        return None
    text = to_text(c["text"])
    first = text.strip().split("\n")[0]
    if first_line_rx and not first_line_rx.search(first):
        return None
    if role_rx and not role_rx.search(text):
        return None
    emails = emails_in(text) or emails_in(deobfuscate(text))
    if not emails:
        return None
    to = emails[0]
    segs = [s.strip() for s in first.split("|")]
    role = next((s for s in segs[1:] if role_rx and role_rx.search(s)), segs[1] if len(segs) > 1 else "")
    loc = next((s for s in segs[1:] if re.search(r"remote|hybrid|onsite|on-site", s, re.I)), "")
    # Evidence: the raw text around the first address (or its obfuscated form).
    local = re.escape(to.split("@")[0])
    m = re.search(local, text, re.I)
    start = max(0, (m.start() if m else 0) - 160)
    evidence = re.sub(r"\s+", " ", text[start:start + 360]).strip()
    posted = datetime.datetime.fromtimestamp(c.get("time", 0), datetime.timezone.utc).date().isoformat()
    return {
        "company": segs[0][:80], "role": role[:120], "url": f"https://news.ycombinator.com/item?id={c['id']}",
        "to": to, "location": loc[:80], "posted_date": posted, "email_source": "comment",
        "evidence": evidence, "all_emails": sorted(set(emails))[:3],
    }


def harvest(thread_ids: Iterable[int], roles: list[str], first_line: str = "", workers: int = 16) -> list[dict]:
    role_rx = re.compile("|".join(f"(?:{r})" for r in roles), re.I) if roles else None
    first_rx = re.compile(first_line, re.I) if first_line else None
    out = []
    for sid in thread_ids:
        story = _get(ITEM.format(sid)) or {}
        kids = story.get("kids", [])
        with cf.ThreadPoolExecutor(workers) as ex:
            for c in ex.map(lambda i: _get(ITEM.format(i)), kids):
                lead = parse_comment(c or {}, role_rx, first_rx)
                if lead:
                    out.append(lead)
    return out
