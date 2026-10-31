# Contributing

Thanks for helping. Hire Lite stays small on purpose: stdlib-only core, one ledger file,
one-line CLI output. Changes that keep it lean are the easiest to merge.

## Setup

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
bash scripts/demo.sh          # end-to-end dry run on synthetic data
python3 scripts/pii_scan.py   # must print "pii-scan: clean"
```

## Ground rules

- **No personal data, ever.** Use synthetic data only: `example.com`/`.org`/`.net` or
  `*.example` / `*.test` domains, placeholder names, no phone numbers, no home paths, no
  real company or recruiter addresses, no real ledgers, logs, resumes or credentials.
  CI runs `scripts/pii_scan.py` and gitleaks on every push and pull request.
- **Core stays stdlib-only** (Python 3.9+). Optional extras go in `requirements.txt` and must
  degrade gracefully when missing.
- **Rules belong in `validate`**, with a test, not only in agent prompts.
- **CLI output stays terse**: one line per command, `report` at most 10 lines.
- **Adapters stay thin**: they point to `AGENTS.md` instead of duplicating it. Do not
  document agent-product features you have not verified.
- Add or update tests for behaviour changes and note user-visible changes in `CHANGELOG.md`.

## Regenerating examples

```bash
python3 examples/make_sample_ledger.py   # rebuilds examples/sample_ledger.jsonl (seeded, synthetic)
```

To refresh `docs/dashboard.png`, render the dashboard from the sample ledger in a temp
directory and capture it with headless Chrome:

```bash
mkdir -p /tmp/hl && cp examples/sample_ledger.jsonl /tmp/hl/ledger.jsonl
python3 hl.py --home /tmp/hl --config config.example.yaml dashboard
google-chrome --headless=new --hide-scrollbars --window-size=1440,1250 \
  --screenshot=docs/dashboard.png file:///tmp/hl/dashboard.html
```

## Pull requests

Keep them focused, describe the behaviour change, and include the test output.
