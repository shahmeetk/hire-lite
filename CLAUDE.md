# Claude Code

Follow the Hire Lite playbook:

@AGENTS.md

Claude Code specifics:

- Run a session with the `/hire-lite-run` slash command (`.claude/commands/hire-lite-run.md`).
- Use your web search/fetch tools for discovery only; read just enough of a page to confirm
  the printed email and copy an evidence snippet.
- Only the commands in the playbook are needed. Ask before anything that sends email for real
  if the user has not approved sending in this session.
- When editing code in this repo, run `python3 -m pytest -q` and `python3 scripts/pii_scan.py`.
