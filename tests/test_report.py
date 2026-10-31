import json
import re
import shutil

from hire_lite import ledger as L
from hire_lite.report import render_dashboard, report_lines, write_dashboard

from .conftest import ROOT, lead, write_harvest


def _sample(cfg, tmp_path):
    shutil.copy(ROOT / "examples" / "sample_ledger.jsonl", tmp_path / "ledger.jsonl")


def test_report_is_terse_and_consistent(cfg, tmp_path):
    _sample(cfg, tmp_path)
    lines = report_lines(cfg)
    assert 1 <= len(lines) <= 10
    recs = L.Ledger(cfg).values()
    emailed = sum(r["status"] in ("sent", "bounced", "dropped") for r in recs)
    assert lines[0].startswith(f"leads {len(recs)} | emailed {emailed} |")
    assert all(len(x) < 300 for x in lines)


def test_report_empty_ledger(cfg):
    lines = report_lines(cfg)
    assert lines[0].startswith("leads 0 | emailed 0 | bounced 0 (0%)")


def test_dashboard_is_static_and_self_contained(cfg, tmp_path):
    _sample(cfg, tmp_path)
    out = write_dashboard(cfg)
    html = out.read_text()
    assert html.startswith("<!doctype html>")
    assert not re.search(r"<(script|link|img)[^>]+(src|href)=", html), "no external resources"
    data = json.loads(re.search(r"const D=(\[.*?\]);", html, re.S).group(1))
    assert len(data) == len(L.Ledger(cfg).values())
    for label in ("Status (all leads)", "Emailed by lane", "Emailed by day", "Top skip reasons", 'id=q', 'id=fs', 'id=fl'):
        assert label in html


def test_dashboard_escapes_hostile_values(cfg, tmp_path):
    L.ingest(cfg, write_harvest(tmp_path / "h.jsonl", lead(company="</script><script>alert(1)</script>")))
    html = render_dashboard(cfg, generated_at="T")
    assert "</script><script>alert(1)" not in html
    assert "<\\/script>" in html
