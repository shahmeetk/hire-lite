import pytest

from hire_lite import config as C

from .conftest import ROOT


def test_mini_yaml_matches_pyyaml_on_example():
    yaml = pytest.importorskip("yaml")
    text = (ROOT / "config.example.yaml").read_text()
    assert C.parse_mini_yaml(text) == yaml.safe_load(text)


def test_mini_yaml_basics():
    data = C.parse_mini_yaml(
        "a: 1\nb: 'x # not a comment'\nc: [one, \"two\"]  # comment\nd:\n  e: true\n  f:\n    - g\n    - h: 2\n      i: no\n"
    )
    assert data == {"a": 1, "b": "x # not a comment", "c": ["one", "two"], "d": {"e": True, "f": ["g", {"h": 2, "i": False}]}}


def test_defaults_without_config(tmp_path):
    cfg = C.load_config(None, tmp_path)
    assert cfg["_config_path"] == ""
    assert cfg["caps"]["export_max"] == 30
    assert "gmail.com" in cfg["free_mail_domains"]
    assert C.path(cfg, "ledger") == tmp_path.resolve() / "ledger.jsonl"


def test_example_config_is_placeholder_only(cfg):
    assert cfg["profile"]["email"].endswith("@example.com")
    assert cfg["profile"]["name"] == "Your Name"


def test_dotenv_does_not_override(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("HL_SMTP_PASSWORD=from-file\nHL_TEST_ONLY='quoted'\n")
    monkeypatch.setenv("HL_SMTP_PASSWORD", "from-env")
    monkeypatch.delenv("HL_TEST_ONLY", raising=False)
    C.load_config(None, tmp_path)
    import os

    assert os.environ["HL_SMTP_PASSWORD"] == "from-env"
    assert os.environ["HL_TEST_ONLY"] == "quoted"
    monkeypatch.delenv("HL_TEST_ONLY")
