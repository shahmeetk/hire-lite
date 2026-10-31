# ChatGPT and Codex

## Codex (CLI, IDE or cloud)

Codex reads `AGENTS.md` from the repository root, so no extra setup is needed. Start a task
with:

> Run one Hire Lite session following AGENTS.md. Stop after export if you cannot reach the
> sender machine.

## ChatGPT with code tools (custom GPT or a chat with file/code execution)

The chat sandbox usually has no access to your mailbox and may have limited network
access, so use it for discovery and ledger work and run the sender on your laptop.

1. Upload `hl.py`, the `hire_lite/` folder (as a zip), your `config.yaml` (without
   secrets), and your current `ledger.jsonl` if you have one.
2. Paste the instructions below (or put them in a custom GPT's instructions).
3. Download the updated `ledger.jsonl` and `outbox.jsonl` at the end (if the sandbox could
   not reach DNS, run `python3 hl.py validate` and `python3 hl.py export` locally first), run
   `bash scripts/hl_send.sh` locally, then run `mark-sent` / `mark-bounced` locally or in
   the next chat.

### Instructions to paste

```text
You run Hire Lite sessions. The rules and procedure are in AGENTS.md (summarized here).
- Do one discovery pass with at most the number of searches in config.yaml caps.discovery_queries.
- Keep a lead only if a hiring email is printed in the post. Never guess or construct emails.
  Never use free-mail addresses. Copy a snippet containing the email into "evidence".
- Lane priority: home region from config.yaml, then fully remote, then hybrid. Skip onsite elsewhere.
- Skip posts that need account creation, OTP, CAPTCHA, Workday-style portals or assessments.
- Never tailor the resume or email template.
- Write leads as JSON lines: company, role, url, to, location, posted_date, email_source, evidence.
- Then run: python3 hl.py ingest <file>; python3 hl.py validate; python3 hl.py export.
  If DNS is unavailable, validate leaves leads pending (dns-pending); say so, and I will
  run validate and export on my laptop.
- Read only the one-line command outputs and `python3 hl.py report`. Never print the ledger.
- Finish with the report lines and tell me which files to download.
```
