---
name: hire-lite
description: Run or maintain the Hire Lite email-first job-apply pipeline (discover leads with printed hiring emails, ingest, validate, export, send, report). Use when the user asks to run a Hire Lite session, check the job-apply report, or handle bounces.
---

# Hire Lite skill

1. `cd` to the Hire Lite repository and read `AGENTS.md`. It is the full procedure.
2. Use only `python3 hl.py <command>` for ledger work. Each command prints one line;
   `report` prints at most 10. Never read the ledger, results or dashboard files in full.
3. Discovery writes `harvest/YYYYMMDD.jsonl` (format in `AGENTS.md`). Only printed emails,
   each with an `evidence` snippet that contains the address.
4. Sending happens only through `scripts/hl_send.sh` on the sender machine. If that machine
   is offline, stop after `export`; validated leads stay queued.
5. Bounces: at most one corrected, published address per bounced lead via `hl.py retry`.
6. End with the report lines and one sentence on anything that needs the user.
