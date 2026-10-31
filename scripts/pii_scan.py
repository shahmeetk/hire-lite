#!/usr/bin/env python3
"""Fail if tracked files contain real-looking email addresses, phone numbers or home paths.

Allowed: RFC 2606/6761 example domains (example.com/.org/.net, *.example, *.test, *.invalid,
localhost). Usage: python3 scripts/pii_scan.py [files...]
"""
import pathlib
import re
import subprocess
import sys

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,})")
PHONE = re.compile(r"(?<![\w.\-/#])\+?\d{1,3}[\s.\-]?\(?\d{2,4}\)?[\s.\-]\d{3,4}[\s.\-]?\d{3,4}(?![\w.\-])")
HOME = re.compile(r"/(?:Users|home)/(?!<|\$|you\b|your)[A-Za-z0-9._\-]+|/workspace/[\w\-]+")
ALLOWED_DOMAIN = re.compile(r"(^|\.)(example\.(com|org|net)|example|test|invalid|localhost)$", re.I)
ALLOWED_EMAIL: set = set()
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"}


def tracked() -> list:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def scan(paths) -> list:
    hits = []
    for p in paths:
        path = pathlib.Path(p)
        if path.suffix.lower() in SKIP_SUFFIX or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in EMAIL.finditer(line):
                if m.group(0).lower() not in ALLOWED_EMAIL and not ALLOWED_DOMAIN.search(m.group(1)):
                    hits.append(f"{p}:{n}: email {m.group(0)}")
            for m in PHONE.finditer(line):
                hits.append(f"{p}:{n}: phone-like {m.group(0)}")
            for m in HOME.finditer(line):
                hits.append(f"{p}:{n}: home path {m.group(0)}")
    return hits


if __name__ == "__main__":
    hits = scan(sys.argv[1:] or tracked())
    print("\n".join(hits) or "pii-scan: clean")
    sys.exit(1 if hits else 0)
