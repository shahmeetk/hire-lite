# Ledger schema

`ledger.jsonl` holds one JSON object per lead, sorted by `first_seen` then `id`. It is the
single source of truth; every other file is derived from it or feeds into it. See
[`examples/sample_ledger.jsonl`](../examples/sample_ledger.jsonl) for synthetic records.

## Record fields

| Field | Type | Description |
|---|---|---|
| `id` | string | `sha1(lower(email) + "\|" + url)[:12]`. Same email + url = same lead |
| `first_seen` | ISO 8601 | When the lead was first ingested (local time with offset) |
| `company` | string | Company name as written in the post |
| `role` | string | Role title; may include a location note like "(Remote)" |
| `location` | string | Location text from the post |
| `lane` | string | First matching lane from `config.yaml` `lanes` (e.g. `home`, `remote`, `hybrid`), or empty |
| `seniority` | string | `head/director`, `principal/architect`, `lead/manager`, `senior`, or `other` |
| `email` | string | Hiring address printed in the post |
| `email_source` | string | Where the address was printed (`post body`, `comment`, `jd page`, or the retry source) |
| `url` | string | Link to the post |
| `posted_date` | string | Post date if known (`YYYY-MM-DD`) |
| `status` | string | See statuses below |
| `reason` | string | Why the lead has its status (skip rule, bounce diagnostic, `ok`, ...) |
| `sent_at` | ISO 8601 | When the sender reported it sent |
| `batch` | string | Harvest file stem, then the outbox batch (`outbox_YYYYMMDD_HHMM`) |
| `attempts` | int | Number of successful sends |
| `method` | string | `email` |
| `evidence` | string | Snippet from the post that contains the address |
| `retry_of` | string | For retry records: the bounced address this record replaces |
| `history` | list | `[{"at", "status", "reason"}, ...]`, one entry per status change |

## Statuses

| Status | Meaning | Set by |
|---|---|---|
| `new` | Ingested, not validated yet (or MX lookup pending) | `ingest` |
| `validated` | Passed every rule; waiting for export/send | `validate` |
| `skipped` | Failed a rule; `reason` says which | `validate`, `migrate` |
| `sent` | Sender reported success | `mark-sent` |
| `bounced` | A bounce arrived; one retry allowed | `mark-bounced` |
| `retry` | Corrected address for a bounced lead, waiting for validation | `retry`, `ingest` |
| `dropped` | A retry bounced too; final | `mark-bounced` |

## Validate rules (in order)

1. `bad syntax/no email`
2. `bounce list` (address in `bounces.txt`)
3. `free-mail` (domain in `free_mail_domains`)
4. `email not in post text` (evidence present but does not contain the address)
5. `no evidence (email must be printed in the post)` (when `validate.require_evidence`)
6. `dup: address already used` (address already sent/bounced/dropped)
7. `dup: url already applied` (new leads only)
8. `dup: same company+role` (new leads only)
9. `excluded company`
10. `role not targeted` (when `targets.roles` is set)
11. `excluded location` (unless the lead is in the first/home lane)
12. `lane unknown/onsite outside home region`
13. `retry exhausted` (retry records only)
14. `no MX` (DNS-over-HTTPS, cached in `mx_cache.json`; lookup errors leave the lead `new`)

## Related files

| File | Format | Written by | Read by |
|---|---|---|---|
| `harvest/YYYYMMDD.jsonl` | `{company, role, url, to, location, posted_date, email_source, evidence}` | agent | `ingest` |
| `outbox.jsonl` | `{id, company, role, url, to, location, lane}` | `export` | `send` |
| `results/results_<ts>.jsonl` | `{date, id, company, role, url, to, result, subject}`; `result` is `sent`, `dry-run` or `error:...` | `send` | `mark-sent` |
| `results/bounces_<ts>.txt` | `address \| reason` per line | `check-bounces` | `mark-bounced` |
| `bounces.txt` | one address per line | `mark-bounced` | `validate` |
| `mx_cache.json` | `{domain: true/false}` | `validate` | `validate` |
| `sent_register.txt` | `YYYY-MM-DD<TAB>address\|url` | `send` | `send` (resend guard, daily cap) |
| `dashboard.html` | static HTML | `dashboard` | you |

All of these are personal data and are git-ignored.

## Legacy import

`hl.py migrate old_log.jsonl ...` imports older send logs with lines like
`{"date", "company", "role", "url", "to", "result": "applied|sent|skipped|blocked", "reason"}`
and upgrades existing records to the current schema (lane, seniority, history).
