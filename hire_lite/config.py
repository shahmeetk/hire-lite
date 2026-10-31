"""Configuration loading.

Config lives in ``config.yaml`` (copy ``config.example.yaml``). PyYAML is used when
installed; otherwise a small built-in parser handles the subset of YAML the example
uses (nested mappings, block/inline lists, quoted or plain scalars, comments).
JSON config files are also accepted.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
from typing import Any

DEFAULT_FREE_MAIL = [
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "icloud.com", "me.com",
    "aol.com", "protonmail.com", "proton.me", "yandex.com", "mail.com", "gmx.com",
    "zohomail.com", "rediffmail.com",
]

DEFAULTS: dict[str, Any] = {
    "profile": {
        "name": "Your Name",
        "email": "you@example.com",
        "headline": "Senior Platform Engineer",
        "base_location": "Your City",
        "notice_period": "30 days",
        "phone": "",
        "links": [],
    },
    "targets": {
        # Regexes matched against the role title (case-insensitive). Empty = accept any.
        "roles": [],
    },
    # Ordered by priority: export sends the first lane first.
    "lanes": [
        {"name": "home", "keywords": []},
        {"name": "remote", "keywords": ["remote", "wfa", "anywhere", "worldwide"]},
        {"name": "hybrid", "keywords": ["hybrid"]},
    ],
    # Onsite locations you never want. Ignored when the lead matches the first (home) lane.
    "excluded_locations": [],
    "excluded_companies": [],
    "free_mail_domains": DEFAULT_FREE_MAIL,
    "validate": {
        "mx_check": True,
        "mx_resolver": "https://dns.google/resolve",
        "mx_timeout_seconds": 8,
        "require_evidence": True,
    },
    "caps": {
        "export_max": 30,
        "send_max_per_run": 30,
        "send_daily_max": 40,
        "send_delay_seconds": 20,
        "discovery_queries": 20,
        "agent_max_turns": 25,
    },
    "sender": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "security": "ssl",  # ssl | starttls | none
        "username": "",  # defaults to profile.email
        "password_env": "HL_SMTP_PASSWORD",
        "keyring_service": "hire-lite-smtp",
        "imap_host": "imap.gmail.com",
        "imap_mailbox": "INBOX",
        "bounce_lookback_days": 7,
        "template_text": "templates/email.txt",
        "template_html": "",
        "attachments": ["resume.pdf"],
        "bounce_wait_seconds": 60,
    },
    "paths": {
        "ledger": "ledger.jsonl",
        "bounces": "bounces.txt",
        "mx_cache": "mx_cache.json",
        "outbox": "outbox.jsonl",
        "results_dir": "results",
        "harvest_dir": "harvest",
        "dashboard": "dashboard.html",
        "sent_register": "sent_register.txt",
    },
}


def _scalar(tok: str) -> Any:
    tok = tok.strip()
    if not tok:
        return None
    if tok[0] in "\"'" and tok[-1] == tok[0] and len(tok) >= 2:
        body = tok[1:-1]
        if tok[0] == "'":
            return body.replace("''", "'")
        esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
        return re.sub(r"\\(.)", lambda m: esc.get(m.group(1), "\\" + m.group(1)), body)
    if tok.startswith("[") and tok.endswith("]"):
        inner = tok[1:-1].strip()
        return [_scalar(x) for x in _split_inline(inner)] if inner else []
    if tok.startswith("{") and tok.endswith("}"):
        out = {}
        for part in _split_inline(tok[1:-1]):
            k, _, v = part.partition(":")
            out[_scalar(k)] = _scalar(v)
        return out
    low = tok.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    if re.fullmatch(r"-?\d+\.\d*", tok):
        return float(tok)
    return tok


def _split_inline(s: str) -> list[str]:
    parts, buf, depth, quote = [], "", 0, ""
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _strip_comment(line: str) -> str:
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def parse_mini_yaml(text: str) -> Any:
    """Parse the YAML subset used by config.example.yaml."""
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))

    def block(i: int, indent: int) -> tuple[Any, int]:
        if i < len(lines) and lines[i][1].startswith("- "):
            items: list[Any] = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                rest = lines[i][1][2:].strip()
                if re.match(r"^[\w.-]+:(\s|$)", rest):
                    # list item that is a mapping: re-parse with the dash as indentation
                    lines[i] = (indent + 2, rest)
                    val, i = mapping(i, indent + 2)
                    items.append(val)
                else:
                    items.append(_scalar(rest))
                    i += 1
            return items, i
        return mapping(i, indent)

    def mapping(i: int, indent: int) -> tuple[dict, int]:
        out: dict[str, Any] = {}
        while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
            key, _, rest = lines[i][1].partition(":")
            key = str(_scalar(key))
            i += 1
            if rest.strip():
                out[key] = _scalar(rest)
            elif i < len(lines) and (lines[i][0] > indent or (lines[i][0] == indent and lines[i][1].startswith("- "))):
                out[key], i = block(i, lines[i][0])
            else:
                out[key] = None
        return out, i

    if not lines:
        return {}
    val, _ = block(0, lines[0][0])
    return val


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        elif v is not None:
            base[k] = v
    return base


def load_dotenv(p: pathlib.Path) -> None:
    """Load KEY=VALUE lines into the environment without overriding variables already set."""
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip().removeprefix("export ").strip(), v.strip()
        if v and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k and v and k not in os.environ:
            os.environ[k] = v


def load_config(path: str | os.PathLike | None = None, home: str | os.PathLike | None = None) -> dict:
    """Load config: explicit path > $HL_CONFIG > <home>/config.yaml > defaults."""
    load_dotenv(pathlib.Path(home or ".").expanduser() / ".env")
    home_p = pathlib.Path(home or os.environ.get("HL_HOME") or ".").expanduser().resolve()
    cand = path or os.environ.get("HL_CONFIG")
    cfg_path = pathlib.Path(cand).expanduser() if cand else home_p / "config.yaml"
    cfg = copy.deepcopy(DEFAULTS)
    if cfg_path.exists():
        text = cfg_path.read_text(encoding="utf-8")
        if cfg_path.suffix == ".json":
            data = json.loads(text)
        else:
            try:
                import yaml  # type: ignore

                data = yaml.safe_load(text)
            except ImportError:
                data = parse_mini_yaml(text)
        _deep_merge(cfg, data or {})
        cfg["_config_path"] = str(cfg_path.resolve())
    else:
        cfg["_config_path"] = ""
    cfg["_home"] = str(home_p)
    return cfg


def resolve(cfg: dict, rel: str) -> pathlib.Path:
    """Resolve a config path relative to the Hire Lite home directory."""
    p = pathlib.Path(rel).expanduser()
    return p if p.is_absolute() else pathlib.Path(cfg["_home"]) / p


def path(cfg: dict, key: str) -> pathlib.Path:
    return resolve(cfg, cfg["paths"][key])
