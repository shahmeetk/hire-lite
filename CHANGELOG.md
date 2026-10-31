# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-31

### Added

- `docs/BOTS.md`: install and first-run steps for Grok Bot, Claude Code, Cursor, and
  ChatGPT/Codex, including the split between the bot and the sender laptop.
- Cursor project rule and `/hire-lite` skill.

### Changed

- The dashboard is a single self-contained page with clickable pipeline counts and charts,
  cross-filters, sortable columns, a per-lead history and evidence panel, and a short
  next-step note.

## [0.1.0] - 2026-10-31

### Added

- Ledger CLI `hl.py` (stdlib only): `init`, `doctor`, `migrate`, `ingest`, `validate`,
  `export`, `mark-sent`, `mark-bounced`, `retry`, `report`, `dashboard`, `send`,
  `check-bounces`, `discover-hn`.
- Validation rules: syntax, bounce list, free-mail block, email-in-evidence (with
  de-obfuscation), duplicate address/url/company+role, excluded companies and locations,
  target roles, configurable lane priority, MX check over DNS-over-HTTPS with cache.
- Lead state machine with per-record history: new, validated, sent, bounced, retry,
  dropped, skipped. One retry per bounce.
- SMTP sender with keychain/env password lookup, dry-run `.eml` previews, per-run and daily
  caps, send delay and resend guard; read-only IMAP bounce checker; `scripts/hl_send.sh`.
- Static, self-contained HTML dashboard and a <=10 line text report.
- Config file with placeholders (`config.example.yaml`, `.env.example`) and editable email
  templates.
- Agent adapters: `AGENTS.md`, Claude Code (`CLAUDE.md`, `/hire-lite-run`), Google
  Antigravity (`.agent/`), Grok Bot routine prompt and skill, ChatGPT/Codex instructions.
- Docs: architecture with Mermaid diagrams, ledger schema, sender setup.
- Synthetic examples, pytest suite, CI with tests, end-to-end dry run, PII scan and gitleaks.
