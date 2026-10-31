---
name: hire-lite
description: Run one Hire Lite session. Discover job posts that print a hiring email, ingest and validate them, export an outbox, and report. Use when the user asks to find jobs, run Hire Lite, apply, or check the pipeline.
---

# Hire Lite

Follow `AGENTS.md` for the full procedure. `docs/BOTS.md` is the human setup guide.

1. Read `config.yaml` once (profile, lanes, caps). If it is missing, say to run `python3 hl.py init` and stop.
2. One discovery pass, at most `caps.discovery_queries` searches. Write `harvest/YYYYMMDD.jsonl` with `company`, `role`, `url`, `to`, `location`, `posted_date`, `email_source`, and `evidence`. The evidence snippet must contain the address. Never guess an email.
3. Run `python3 hl.py ingest`, `validate`, and `export`.
4. If the user said dry-run, or has not approved sending, run `bash scripts/hl_send.sh --dry-run` and do not mark anything sent. Otherwise run `bash scripts/hl_send.sh`, then `mark-sent` and `mark-bounced` on the two files it names.
5. Finish with `python3 hl.py report` and one sentence on anything queued or bounced. Do not print the ledger.
