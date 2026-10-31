"""MX lookup over DNS-over-HTTPS (stdlib only)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

MX_TYPE = 15


def has_mx(domain: str, resolver: str = "https://dns.google/resolve", timeout: float = 8) -> Optional[bool]:
    """True if the domain publishes a usable MX, False if not, None if the lookup failed.

    A "null MX" (``0 .``, RFC 7505) means the domain accepts no mail and counts as False.
    """
    url = f"{resolver}?{urllib.parse.urlencode({'name': domain, 'type': 'MX'})}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception:
        return None
    if data.get("Status") == 3:  # NXDOMAIN
        return False
    if data.get("Status") != 0:
        return None
    answers = [a for a in data.get("Answer", []) if a.get("type") == MX_TYPE]
    usable = [a for a in answers if str(a.get("data", "")).split()[-1:] != ["."]]
    return bool(usable)
