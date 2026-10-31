# Hire Lite agent playbook

You are running one Hire Lite session for the user: find job posts that print a hiring
email, record them in the ledger, and hand a validated outbox to the sender. The CLI
(`python3 hl.py ...`) does all bookkeeping with zero LLM calls. Your job is discovery and
judgement; keep everything else mechanical and cheap.

- Source of truth: `ledger.jsonl` in the Hire Lite home (`$HL_HOME`, default the repo root).
- Settings: `config.yaml` (profile, target roles, lane priority, exclusions, caps). Read it once.
- Every CLI command prints one line; `hl.py report` prints at most 10. That is all you read.

## Hard rules

1. **Never guess an email.** Use only an address printed in the post, its comments, or the
   linked job description. No pattern guessing (`firstname@`), no enrichment tools, no
   free-mail addresses. Copy the text around the address into `evidence`.
2. **Respect lane priority** from `config.yaml`: the first lane (home region), then fully
   remote, then hybrid. Onsite roles outside the home region are skipped (`validate` enforces).
3. **Skip walls.** Do not proceed with posts that need account creation, OTP/SMS codes,
   CAPTCHA, Workday or similar ATS portals, or assessments before applying. Email only.
4. **Fixed resume.** Never edit, tailor or regenerate the resume or the template per job.
5. **Respect sites.** Follow each site's terms of service and robots rules, prefer official
   APIs/feeds, and never log in on the user's behalf to scrape.
6. **One retry per bounce.** A bounced lead may get one corrected address that is itself
   published somewhere (`hl.py retry`). A second bounce drops the lead.
7. **Stay within caps** (`caps` in `config.yaml`): at most `discovery_queries` searches,
   `export_max` leads per outbox, `agent_max_turns` tool calls per session. Stop when a cap is hit.

## Run procedure

Run from the Hire Lite home. Replace `YYYYMMDD` with today's date.

1. **Discover (one pass).** Run at most `caps.discovery_queries` searches across cheap
   sources (job boards with public listings, "who is hiring" threads, company career
   pages). Optional helper: `python3 hl.py discover-hn --first-line remote` writes
   candidates to `harvest/hn_candidates_YYYYMMDD.jsonl`; review them, keep the good ones.
   Write `harvest/YYYYMMDD.jsonl`, one JSON object per line:

   ```json
   {"company": "Acme", "role": "Senior Platform Engineer (Remote)", "url": "https://...",
    "to": "careers@acme.example.com", "location": "Remote", "posted_date": "2026-11-01",
    "email_source": "post body|comment|jd page", "evidence": "<snippet containing the email>"}
   ```

   Put the location in `location` (or in the role, e.g. "(Remote)", "(Hybrid, City)").
2. `python3 hl.py ingest harvest/YYYYMMDD.jsonl` (dedupes against the ledger; a new address
   for a bounced lead becomes `retry`).
3. `python3 hl.py validate` (syntax, bounce list, free-mail, email-in-evidence, duplicates,
   excluded companies/locations, target roles, lane, MX via DNS-over-HTTPS).
4. `python3 hl.py export` (writes `outbox.jsonl`, home lane first, capped at `caps.export_max`).
5. **Send.** Either:
   - same machine: `bash scripts/hl_send.sh` (add `--dry-run` to preview only), or
   - separate sender laptop: copy `outbox.jsonl` into that laptop's Hire Lite home, run
     `bash scripts/hl_send.sh` there, and copy back the two files named on its last line
     (`results/results_<ts>.jsonl`, `results/bounces_<ts>.txt`).
6. `python3 hl.py mark-sent results/results_<ts>.jsonl` then
   `python3 hl.py mark-bounced results/bounces_<ts>.txt`.
7. **Bounces.** For each newly bounced lead, look once (post, company careers/contact page)
   for a different *published* address. If found:
   `python3 hl.py retry <bounced> <corrected> "<where found>" --evidence "<snippet>"`, then
   `validate` and `export` again next run. If not found, leave it bounced.
8. `python3 hl.py report` and `python3 hl.py dashboard`.
9. Send the user one short message: the report lines plus anything that needs a human
   (for example "sender offline, 12 queued").

### Sender offline

Stop after step 4. Validated leads stay `validated` in the ledger and are exported again
next run. Do not retry the sender in a loop and do not invent another send path.

## Token rules

- One discovery pass per session; reuse the helpers in this repo, do not write new
  versioned scripts.
- Never `cat` the ledger, logs, results or dashboard. Read only CLI one-liners and `report`.
- No browser automation for applying, no screenshots, no page dumps; fetch a page only to
  confirm a printed email and copy a short evidence snippet.
- Do not re-validate or re-search leads already in the ledger; `ingest` handles dedupe.
- One short summary message per session.

## Never

- Send anything outside `scripts/hl_send.sh` / `hl.py send`, or change caps to send more.
- Commit `config.yaml`, `.env`, `ledger.jsonl`, `harvest/`, `results/`, `outbox*`, resumes or logs.
- Put personal data (names, emails, phone numbers, home paths) in tracked files.
