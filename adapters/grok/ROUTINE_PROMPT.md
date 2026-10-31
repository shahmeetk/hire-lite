# Grok Bot routine prompt

Use this as the prompt of a recurring task (reference schedule: Monday, Wednesday and
Friday at 12:00 in your time zone). Adjust the paths in angle brackets. If your Grok Bot
setup does not support scheduled tasks, run the same prompt manually.

---

You run Hire Lite for me. The repository is at `<path to your hire-lite clone>`.
Read `AGENTS.md` there and follow its run procedure and rules exactly. Key points:

- One discovery pass, at most the `caps.discovery_queries` searches set in `config.yaml`.
- Only use hiring emails printed in the post, with an evidence snippet. Never guess.
- Lane priority: my home region, then fully remote, then hybrid.
- Skip anything behind account creation, OTP, CAPTCHA, Workday-style portals or assessments.
- Never tailor the resume or the template.
- Run the `python3 hl.py` steps in order. If the sender laptop is offline, stop after
  `export` and tell me how many leads are queued.
- Read only the one-line CLI outputs and `python3 hl.py report`.
- Finish with one short message to me: the report lines and anything that needs me.
