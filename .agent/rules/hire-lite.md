---
trigger: always_on
description: Hire Lite rules for agents working in this workspace
---

# Hire Lite workspace rules

- The full procedure and rules are in `AGENTS.md` at the workspace root. Follow it.
- Never guess an email address. Only use addresses printed in the post, with an evidence snippet.
- Skip posts behind account creation, OTP, CAPTCHA, Workday-style portals or assessments.
- Never tailor or edit the resume or email template per job.
- Read only the one-line CLI outputs and `python3 hl.py report`; never open the ledger,
  results, logs or dashboard in full.
- Never commit `config.yaml`, `.env`, `ledger.jsonl`, `harvest/`, `results/`, `outbox*` or resumes.
