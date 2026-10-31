---
description: Run one Hire Lite session (discover, ingest, validate, export, send, report)
---

1. Read `config.yaml` once for target roles, lane priority and caps.
2. Do one discovery pass (at most `caps.discovery_queries` searches). Write qualifying leads
   to `harvest/YYYYMMDD.jsonl` in the format shown in `AGENTS.md`, with an evidence snippet
   that contains the printed email.
3. Run `python3 hl.py ingest harvest/YYYYMMDD.jsonl`.
4. Run `python3 hl.py validate`.
5. Run `python3 hl.py export`.
6. If the sender runs on this machine, run `bash scripts/hl_send.sh` (ask the user first if
   real sending has not been approved; use `--dry-run` otherwise). If it runs elsewhere,
   stop here and report that the outbox is ready.
7. Run `python3 hl.py mark-sent <results file>` and `python3 hl.py mark-bounced <bounces file>`
   with the two files printed by the sender.
8. For new bounces, follow the one-retry rule in `AGENTS.md`.
9. Run `python3 hl.py report` and `python3 hl.py dashboard`, then send the user the report lines.
