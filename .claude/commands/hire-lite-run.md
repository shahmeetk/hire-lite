---
description: Run one Hire Lite session (discover, ingest, validate, export, send, report)
argument-hint: "[dry-run] [max leads]"
---

Run one Hire Lite session following `AGENTS.md` exactly. Arguments: $ARGUMENTS

- If the arguments contain `dry-run`, pass `--dry-run` to `scripts/hl_send.sh` and skip
  `mark-sent` / `mark-bounced`.
- If a number is given, use it as `--max` for `export` (never above `caps.export_max`).
- If the sender runs on another machine, stop after `export` and tell me the outbox is ready.

Finish with the `python3 hl.py report` lines and one sentence on anything that needs me.
