import importlib.util
import json

from hire_lite.cli import main
from hire_lite.discovery import hn

from .conftest import ROOT


def test_cli_end_to_end_dry_run(tmp_path, capsys):
    (tmp_path / "config.yaml").write_text((ROOT / "config.example.yaml").read_text())
    import shutil

    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    h = ["--home", str(tmp_path)]
    assert main(h + ["ingest", str(ROOT / "examples/harvest/20261102.jsonl")]) == 0
    assert main(h + ["validate", "--skip-mx"]) == 0
    assert main(h + ["export"]) == 0
    assert main(h + ["send", "--dry-run"]) == 0
    assert main(h + ["report"]) == 0
    assert main(h + ["dashboard"]) == 0
    out = capsys.readouterr().out
    assert "ingest added=12 dup=1" in out
    assert "validate skipped=6 validated=6" in out
    assert "dry-run=6" in out
    assert (tmp_path / "dashboard.html").exists()
    assert main(h + ["retry", "nobody@x.example.com", "a@x.example.com", "site"]) == 1


def test_hn_parse_comment():
    c = {"id": 42, "time": 1790000000,
         "text": "Acme | Senior SRE | Remote (EU) | https://acme.example.com<p>Email jobs [at] acme [dot] example [dot] com"}
    got = hn.parse_comment(c, hn.re.compile("sre", hn.re.I), hn.re.compile("remote", hn.re.I))
    assert got["company"] == "Acme" and got["role"] == "Senior SRE" and got["location"] == "Remote (EU)"
    assert got["to"] == "jobs@acme.example.com" and "jobs [at] acme" in got["evidence"]
    assert hn.parse_comment(dict(c, text="Acme | SRE | Onsite<p>no email"), None, None) is None


def _scanner():
    spec = importlib.util.spec_from_file_location("pii_scan", ROOT / "scripts" / "pii_scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pii_scanner_flags_and_allows(tmp_path):
    scan = _scanner()
    bad = tmp_path / "bad.txt"
    # Fabricated values, assembled at runtime so the scanner does not flag this test file.
    at, users = "@", "/" + "Users/"
    bad.write_text(f"mail me: jane.doe{at}realcorp.io\ncall +1 415 555 {2671}\npath {users}jane/notes\n")
    good = tmp_path / "good.txt"
    good.write_text("you@example.com jobs@acme.example.com a@b.test id=1790000000 2026-10-31T12:00:00+01:00\n")
    hits = scan.scan([str(bad), str(good)])
    assert len(hits) == 3 and all("bad.txt" in h for h in hits)


def test_examples_are_synthetic():
    scan = _scanner()
    files = [str(p) for p in (ROOT / "examples").rglob("*") if p.is_file()]
    assert scan.scan(files) == []
    for line in open(ROOT / "examples/sample_ledger.jsonl"):
        assert json.loads(line)["email"].endswith(".example.com") or not json.loads(line)["email"]
