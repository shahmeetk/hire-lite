import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hire_lite import config as C  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    c = C.load_config(ROOT / "config.example.yaml", tmp_path)
    c["caps"]["send_delay_seconds"] = 0
    return c


@pytest.fixture
def mx_ok():
    calls = []

    def lookup(domain):
        calls.append(domain)
        return True

    lookup.calls = calls
    return lookup


def lead(**kw):
    base = dict(company="Acme", role="Senior Platform Engineer", url="https://jobs.example.com/1",
                to="jobs@acme.example.com", location="Remote", posted_date="2026-10-01",
                email_source="post body")
    base.update(kw)
    base.setdefault("evidence", f"Send CVs to {base['to']}")
    return base


def write_harvest(path, *leads):
    path.write_text("".join(json.dumps(x) + "\n" for x in leads))
    return str(path)
