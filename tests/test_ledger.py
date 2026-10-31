import json

import pytest

from hire_lite import ledger as L

from .conftest import lead, write_harvest


def statuses(cfg):
    return {r["company"]: (r["status"], r["reason"]) for r in L.Ledger(cfg).values()}


# ------------------------------------------------------------------ ingest / dedupe

def test_ingest_adds_and_dedupes(cfg, tmp_path):
    f = write_harvest(tmp_path / "h.jsonl", lead(), lead(), lead(company="Globex", url="https://jobs.example.com/2",
                                                                 to="sre@globex.example.com"))
    with open(f, "a") as fh:
        fh.write("not json\n\n")
    assert L.ingest(cfg, f) == {"added": 2, "dup": 1, "bad-json": 1}
    assert L.ingest(cfg, f) == {"dup": 3, "bad-json": 1}
    recs = L.Ledger(cfg).values()
    assert {r["batch"] for r in recs} == {"h"}
    assert all(r["history"][0]["status"] == "new" for r in recs)


def test_ingest_derives_lane_and_seniority(cfg, tmp_path):
    f = write_harvest(tmp_path / "h.jsonl",
                      lead(role="Head of Platform (Springfield)", location=""),
                      lead(company="B", role="Staff SRE", url="u2", to="b@b.example.com", location="Hybrid, Capital City"),
                      lead(company="C", role="DevOps Engineer", url="u3", to="c@c.example.com", location="Remote"))
    L.ingest(cfg, f)
    got = {r["company"]: (r["lane"], r["seniority"]) for r in L.Ledger(cfg).values()}
    assert got == {"Acme": ("home", "head/director"), "B": ("hybrid", "principal/architect"), "C": ("remote", "other")}


def test_ledger_writes_are_atomic_and_sorted(cfg, tmp_path):
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead()))
    p = cfg["_home"] + "/ledger.jsonl"
    lines = open(p).read().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["status"] == "new"
    assert not (tmp_path / "ledger.jsonl.tmp").exists()


# ------------------------------------------------------------------ validate rules

@pytest.mark.parametrize("override,reason", [
    (dict(to="not-an-email", evidence="x"), "bad syntax/no email"),
    (dict(to=""), "bad syntax/no email"),
    (dict(to="me@freemail.test", evidence="me@freemail.test"), "free-mail"),
    (dict(evidence="Apply on our portal"), "email not in post text"),
    (dict(evidence=""), "no evidence (email must be printed in the post)"),
    (dict(company="Current Employer Inc"), "excluded company"),
    (dict(role="Marketing Manager"), "role not targeted"),
    (dict(location="Ogdenville (onsite)"), "excluded location"),
    (dict(location="Capital City (onsite)"), "lane unknown/onsite outside home region"),
])
def test_validate_rules(cfg, tmp_path, mx_ok, override, reason):
    cfg["free_mail_domains"] = cfg["free_mail_domains"] + ["freemail.test"]
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead(**override)))
    L.validate(cfg, mx_lookup=mx_ok)
    (rec,) = L.Ledger(cfg).values()
    assert (rec["status"], rec["reason"]) == ("skipped", reason)


def test_default_free_mail_list_covers_big_providers(cfg):
    assert {"gmail.com", "outlook.com", "yahoo.com", "icloud.com"} <= set(cfg["free_mail_domains"])


def test_home_lane_overrides_excluded_location(cfg, tmp_path, mx_ok):
    cfg["excluded_locations"] = ["springfield"]
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead(location="Springfield")))
    L.validate(cfg, mx_lookup=mx_ok)
    assert statuses(cfg)["Acme"] == ("validated", "ok")


def test_validate_accepts_obfuscated_evidence(cfg, tmp_path, mx_ok):
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead(evidence="mail jobs [at] acme [dot] example [dot] com")))
    L.validate(cfg, mx_lookup=mx_ok)
    assert statuses(cfg)["Acme"][0] == "validated"


def test_bounce_list_blocks(cfg, tmp_path, mx_ok):
    (tmp_path / "bounces.txt").write_text("jobs@acme.example.com\n")
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead()))
    L.validate(cfg, mx_lookup=mx_ok)
    assert statuses(cfg)["Acme"] == ("skipped", "bounce list")


def test_mx_results_and_cache(cfg, tmp_path):
    seen = []

    def lookup(d):
        seen.append(d)
        return {"good.example.com": True, "nomx.example.com": False}.get(d)  # anything else: lookup failed

    f = write_harvest(tmp_path / "h.jsonl",
                      lead(company="A", url="1", to="a@good.example.com"),
                      lead(company="B", url="2", to="b@good.example.com", role="Staff SRE"),
                      lead(company="C", url="3", to="c@nomx.example.com"),
                      lead(company="D", url="4", to="d@down.example.com"))
    L.ingest(cfg, f)
    assert L.validate(cfg, mx_lookup=lookup) == {"validated": 2, "skipped": 1, "dns-pending": 1}
    assert seen.count("good.example.com") == 1
    st = statuses(cfg)
    assert st["C"] == ("skipped", "no MX") and st["D"][0] == "new"
    cache = json.loads((tmp_path / "mx_cache.json").read_text())
    assert cache == {"good.example.com": True, "nomx.example.com": False}
    seen.clear()
    L.validate(cfg, mx_lookup=lambda d: True)
    assert statuses(cfg)["D"][0] == "validated"


def test_skip_mx_never_calls_lookup(cfg, tmp_path):
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead()))
    L.validate(cfg, mx_lookup=lambda d: pytest.fail("lookup called"), skip_mx=True)
    assert statuses(cfg)["Acme"][0] == "validated"


def _send_all(cfg, tmp_path, mx_ok):
    L.validate(cfg, mx_lookup=mx_ok)
    n, out, _ = L.export(cfg)
    res = tmp_path / "res.jsonl"
    res.write_text("".join(json.dumps(dict(json.loads(x), result="sent", date="2026-10-02T12:00:00+00:00")) + "\n"
                           for x in out.read_text().splitlines()))
    return L.mark_sent(cfg, [str(res)])


@pytest.mark.parametrize("override,reason", [
    (dict(url="https://jobs.example.com/other", role="Other Platform Role"), "dup: address already used"),
    (dict(to="other@acme.example.com"), "dup: url already applied"),
    (dict(to="other@acme.example.com", url="https://jobs.example.com/new"), "dup: same company+role"),
])
def test_dedupe_against_sent(cfg, tmp_path, mx_ok, override, reason):
    L.ingest(cfg, write_harvest(tmp_path / "a.jsonl", lead()))
    _send_all(cfg, tmp_path, mx_ok)
    L.ingest(cfg, write_harvest(tmp_path / "b.jsonl", lead(**override)))
    L.validate(cfg, mx_lookup=mx_ok)
    newest = [r for r in L.Ledger(cfg).values() if r["batch"] == "b"][0]
    assert (newest["status"], newest["reason"]) == ("skipped", reason)


# ------------------------------------------------------------------ export / mark-sent

def test_export_orders_by_lane_priority_and_caps(cfg, tmp_path, mx_ok):
    f = write_harvest(tmp_path / "h.jsonl",
                      lead(company="H1", url="1", to="a@h1.example.com", location="Hybrid, Capital City"),
                      lead(company="R1", url="2", to="a@r1.example.com", location="Remote"),
                      lead(company="M1", url="3", to="a@m1.example.com", location="Springfield"),
                      lead(company="R2", url="4", to="a@r2.example.com", location="Remote"))
    L.ingest(cfg, f)
    L.validate(cfg, mx_lookup=mx_ok)
    n, out, batch = L.export(cfg, 3)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert n == 3 and [r["lane"] for r in rows] == ["home", "remote", "remote"]
    assert rows[0]["company"] == "M1"
    assert batch.startswith("outbox_")
    assert {r["status"] for r in L.Ledger(cfg).values()} == {"validated"}


def test_mark_sent_ignores_dry_run_and_counts_errors(cfg, tmp_path, mx_ok):
    f = write_harvest(tmp_path / "h.jsonl", lead(), lead(company="B", url="2", to="b@b.example.com"),
                      lead(company="C", url="3", to="c@c.example.com"))
    L.ingest(cfg, f)
    L.validate(cfg, mx_lookup=mx_ok)
    _, out, _ = L.export(cfg)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    res = tmp_path / "res.jsonl"
    res.write_text("\n".join(json.dumps(dict(r, result=x, date="2026-10-02T12:00:00+00:00"))
                             for r, x in zip(rows, ["sent", "dry-run", "error:550"])))
    assert L.mark_sent(cfg, [str(res)]) == (1, 1)
    st = statuses(cfg)
    assert st["Acme"] == ("sent", "sent") and st["B"][0] == "validated" and st["C"][0] == "validated"
    sent = [r for r in L.Ledger(cfg).values() if r["status"] == "sent"][0]
    assert sent["sent_at"] == "2026-10-02T12:00:00+00:00" and sent["attempts"] == 1
    assert [h["status"] for h in sent["history"]] == ["new", "validated", "sent"]


# ------------------------------------------------------------------ bounce / retry

def test_one_retry_per_bounce_then_dropped(cfg, tmp_path, mx_ok):
    L.ingest(cfg, write_harvest(tmp_path / "a.jsonl", lead()))
    _send_all(cfg, tmp_path, mx_ok)
    bf = tmp_path / "bounces_1.txt"
    bf.write_text("jobs@acme.example.com | 550 5.1.1 user unknown\n")
    assert L.mark_bounced(cfg, [str(bf)]) == (1, 1)
    assert statuses(cfg)["Acme"][0] == "bounced"
    assert "550 5.1.1" in statuses(cfg)["Acme"][1]

    with pytest.raises(ValueError):
        L.retry(cfg, "jobs@acme.example.com", "careers@acme.example.com", "")  # must say where it was found
    r = L.retry(cfg, "jobs@acme.example.com", "careers@acme.example.com", "careers page")
    assert r["status"] == "retry" and r["retry_of"] == "jobs@acme.example.com"
    with pytest.raises(ValueError, match="already used"):
        L.retry(cfg, "jobs@acme.example.com", "hr@acme.example.com", "about page")

    _send_all(cfg, tmp_path, mx_ok)
    L.mark_bounced(cfg, ["careers@acme.example.com"])
    rec = [x for x in L.Ledger(cfg).values() if x["email"] == "careers@acme.example.com"][0]
    assert (rec["status"], rec["reason"]) == ("dropped", "retry bounced; dropped")
    with pytest.raises(ValueError):
        L.retry(cfg, "careers@acme.example.com", "hr@acme.example.com", "about page")


def test_ingest_corrected_address_becomes_retry_once(cfg, tmp_path, mx_ok):
    L.ingest(cfg, write_harvest(tmp_path / "a.jsonl", lead()))
    _send_all(cfg, tmp_path, mx_ok)
    L.mark_bounced(cfg, ["jobs@acme.example.com"])
    L.ingest(cfg, write_harvest(tmp_path / "b.jsonl", lead(to="careers@acme.example.com"),
                                lead(to="hr@acme.example.com")))
    recs = {r["email"]: r for r in L.Ledger(cfg).values()}
    assert recs["careers@acme.example.com"]["status"] == "retry"
    assert recs["hr@acme.example.com"]["status"] == "retry"
    L.validate(cfg, mx_lookup=mx_ok)
    recs = {r["email"]: r for r in L.Ledger(cfg).values()}
    got = sorted((recs[e]["status"], recs[e]["reason"]) for e in ("careers@acme.example.com", "hr@acme.example.com"))
    assert got == [("skipped", "retry exhausted"), ("validated", "retry of jobs@acme.example.com")]


def test_migrate_imports_legacy_log(cfg, tmp_path):
    legacy = tmp_path / "old_log.jsonl"
    legacy.write_text(
        json.dumps(dict(date="2026-09-01T10:00:00", company="Old Co", role="SRE Lead (Remote)", url="u1",
                        to="jobs@oldco.example.com", result="applied")) + "\n"
        + json.dumps(dict(date="2026-09-01T10:05:00", company="Wall Co", role="DevOps", url="u2",
                          result="blocked", reason="account required")) + "\n")
    (tmp_path / "bounces.txt").write_text("jobs@oldco.example.com\n")
    assert L.migrate(cfg, [str(legacy)]) == {"imported": 2, "bounced": 1}
    st = statuses(cfg)
    assert st["Old Co"][0] == "bounced" and st["Wall Co"] == ("skipped", "account required")
    assert L.migrate(cfg, [str(legacy)])["merged"] == 2
