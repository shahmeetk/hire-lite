import email
import io
import json

import pytest

from hire_lite import bounces, mx, sender
from hire_lite import ledger as L

from .conftest import lead, write_harvest


def _outbox(cfg, tmp_path, n=3):
    leads = [lead(company=f"Co{i}", url=f"https://jobs.example.com/{i}", to=f"jobs@co{i}.example.com",
                  role="Staff SRE (Remote)") for i in range(n)]
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", *leads))
    L.validate(cfg, skip_mx=True)
    L.export(cfg)


class FakeSMTP:
    def __init__(self):
        self.sent, self.logged_in = [], None

    def login(self, user, pw):
        self.logged_in = (user, pw)

    def send_message(self, m):
        if "co1." in m["To"]:
            raise RuntimeError("550 rejected")
        self.sent.append(m)

    def quit(self):
        pass


def test_dry_run_writes_previews_and_sends_nothing(cfg, tmp_path):
    _outbox(cfg, tmp_path)
    r = sender.send(cfg, dry_run=True, smtp_factory=lambda: pytest.fail("SMTP used in dry run"))
    assert r["dry-run"] == 3 and r["sent"] == 0
    emls = sorted((tmp_path / "results").glob("preview_*/*.eml"))
    assert len(emls) == 3
    msg = email.message_from_bytes(emls[0].read_bytes())
    assert msg["Subject"].startswith("Staff SRE | Your Name")
    body = msg.get_payload(decode=True).decode()
    assert "Hi Co" in body and "$" not in body and "remote work" in body
    results = [json.loads(x) for x in open(r["results"])]
    assert {x["result"] for x in results} == {"dry-run"}
    assert L.mark_sent(cfg, [r["results"]]) == (0, 0)


def test_send_records_results_and_never_resends(cfg, tmp_path, monkeypatch):
    _outbox(cfg, tmp_path)
    (tmp_path / "resume.pdf").write_bytes(b"%PDF-1.4 synthetic")
    monkeypatch.setenv("HL_SMTP_PASSWORD", "abcd efgh")
    fake = FakeSMTP()
    r = sender.send(cfg, smtp_factory=lambda: fake, sleep=lambda s: None)
    assert (r["sent"], r["errors"]) == (2, 1)
    assert fake.logged_in == ("you@example.com", "abcdefgh")
    assert fake.sent[0].get_content_maintype() == "multipart"
    assert [a.get_filename() for a in fake.sent[0].iter_attachments()] == ["resume.pdf"]
    assert L.mark_sent(cfg, [r["results"]]) == (2, 1)
    r2 = sender.send(cfg, smtp_factory=lambda: fake, sleep=lambda s: None)
    assert r2["skipped"] == 2 and r2["sent"] == 0


def test_daily_cap(cfg, tmp_path, monkeypatch):
    _outbox(cfg, tmp_path, n=4)
    (tmp_path / "resume.pdf").write_bytes(b"x")
    monkeypatch.setenv("HL_SMTP_PASSWORD", "pw")
    cfg["caps"]["send_daily_max"] = 2
    fake = FakeSMTP()
    r = sender.send(cfg, smtp_factory=lambda: fake, sleep=lambda s: None)
    assert r["sent"] + r["errors"] == 2


def test_missing_attachment_blocks_real_send(cfg, tmp_path, monkeypatch):
    _outbox(cfg, tmp_path)
    monkeypatch.setenv("HL_SMTP_PASSWORD", "pw")
    with pytest.raises(FileNotFoundError):
        sender.send(cfg, smtp_factory=FakeSMTP)


def test_pick_highlights_prefers_matching_lines():
    hl = [dict(match="cloud", text="A"), dict(match="sre|reliab", text="B"), dict(match="ml", text="C")]
    assert sender.pick_highlights("Senior SRE", hl, 2) == ["B", "A"]


DSN = b"""From: Mail Delivery Subsystem <mailer-daemon@mail.example.com>
To: you@example.com
Subject: Delivery Status Notification (Failure)
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"

--b1
Content-Type: text/plain

Your message wasn't delivered to jobs@gone.example.com because the address couldn't be found.

--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.example.com

Final-Recipient: rfc822; jobs@gone.example.com
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp; 550 5.1.1 The email account does not exist

--b1--
"""


def test_parse_bounce_dsn():
    assert bounces.parse_bounce(DSN) == {"jobs@gone.example.com": "smtp; 550 5.1.1 The email account does not exist"}


def test_parse_bounce_human_text_only():
    raw = b"Subject: Undeliverable\n\nYour message wasn't delivered to hr@old.example.com because it was not found.\n"
    assert bounces.parse_bounce(raw) == {"hr@old.example.com": "address not found"}


def test_parse_bounce_lines():
    got = L.parse_bounce_lines("a@x.example.com | 550 user unknown\nTOTAL 1\nb@y.example.com\n")
    assert got == {"a@x.example.com": "550 user unknown", "b@y.example.com": ""}


@pytest.mark.parametrize("payload,expected", [
    ({"Status": 0, "Answer": [{"type": 15, "data": "10 mx1.example.com."}]}, True),
    ({"Status": 0, "Answer": [{"type": 15, "data": "0 ."}]}, False),
    ({"Status": 0}, False),
    ({"Status": 3}, False),
    ({"Status": 2}, None),
])
def test_has_mx_parsing(monkeypatch, payload, expected):
    monkeypatch.setattr(mx.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    assert mx.has_mx("example.com") is expected


def test_has_mx_network_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(mx.urllib.request, "urlopen", boom)
    assert mx.has_mx("example.com") is None
