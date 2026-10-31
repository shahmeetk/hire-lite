"""Find delivery-failure notices (DSNs) in the sender's mailbox over IMAP (read-only)."""
from __future__ import annotations

import datetime
import email
import imaplib
import re
from email.message import Message

from .credentials import get_password

FINAL_RCPT = re.compile(r"(?:Final|Original)-Recipient:\s*rfc822;\s*<?([^\s>]+@[^\s>]+)", re.I)
ADDR = r"[\w.%+\-]+@[\w\-]+(?:\.[\w\-]+)+"
HUMAN_RCPT = [
    re.compile(rf"wasn't delivered to\s+<?({ADDR})", re.I),
    re.compile(rf"delivery to the following recipients? failed[^\n]*\n\s*<?({ADDR})", re.I),
    re.compile(rf"could not be delivered to\s+<?({ADDR})", re.I),
]


def _body(msg: Message) -> str:
    out = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/plain", "message/delivery-status"):
            payload = part.get_payload(decode=True)
            if payload:
                out.append(payload.decode("utf-8", "ignore"))
            elif ctype == "message/delivery-status":
                out.extend(str(p) for p in part.get_payload() if p)
    return "\n".join(out)


def parse_bounce(raw: bytes) -> dict[str, str]:
    """Return {failed_address: short_reason} from one raw RFC822 bounce message."""
    body = _body(email.message_from_bytes(raw))
    addrs = FINAL_RCPT.findall(body)
    if not addrs:
        for rx in HUMAN_RCPT:
            addrs += rx.findall(body)
    m = re.search(r"Diagnostic-Code:\s*([^\n]{0,160})", body)
    if m:
        reason = m.group(1).strip()
    elif re.search(r"not found|couldn't be found|does not exist|no such user", body, re.I):
        reason = "address not found"
    else:
        reason = "delivery failed"
    return {a.strip("<>.,;").lower(): reason for a in addrs}


def check_bounces(cfg: dict, since_days: int | None = None) -> dict[str, str]:
    s = cfg["sender"]
    days = s.get("bounce_lookback_days", 7) if since_days is None else since_days
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    pw = get_password(cfg)
    if not pw:
        raise RuntimeError("no mailbox password (see sender.password_env / keyring_service)")
    imap = imaplib.IMAP4_SSL(s["imap_host"])
    try:
        imap.login(s.get("username") or cfg["profile"]["email"], pw)
        pw = None
        imap.select(f'"{s.get("imap_mailbox", "INBOX")}"', readonly=True)
        _, data = imap.search(None, f'(SINCE {since} OR FROM "mailer-daemon" FROM "postmaster")')
        found: dict[str, str] = {}
        for num in data[0].split():
            _, msg_data = imap.fetch(num, "(BODY.PEEK[])")
            for k, v in parse_bounce(msg_data[0][1]).items():
                found.setdefault(k, v)
        return found
    finally:
        try:
            imap.logout()
        except Exception:
            pass
