# Agent adapters

Hire Lite is agent-agnostic. Every adapter is a thin pointer to [`AGENTS.md`](../AGENTS.md),
which holds the run procedure, hard rules and token rules. Keep adapters short so the
playbook has one source of truth.

| Agent | Files | How it is used |
|---|---|---|
| Grok Bot | [`grok/ROUTINE_PROMPT.md`](grok/ROUTINE_PROMPT.md), [`grok/skills/hire-lite/SKILL.md`](grok/skills/hire-lite/SKILL.md) | Paste the routine prompt into a scheduled task; add the skill if your setup supports skills |
| Claude Code | [`CLAUDE.md`](../CLAUDE.md), [`.claude/commands/hire-lite-run.md`](../.claude/commands/hire-lite-run.md) | Loaded automatically in the repo; run `/hire-lite-run` |
| ChatGPT / Codex | [`AGENTS.md`](../AGENTS.md), [`chatgpt/INSTRUCTIONS.md`](chatgpt/INSTRUCTIONS.md) | Codex reads `AGENTS.md`; for a custom GPT or chat with code tools, paste the instructions |
| Google Antigravity | [`.agent/rules/hire-lite.md`](../.agent/rules/hire-lite.md), [`.agent/workflows/hire-lite-run.md`](../.agent/workflows/hire-lite-run.md) | Workspace rule plus a run workflow |

Agent products change quickly. If your version looks for rules, commands or skills in a
different place, copy the same content there; the content matters, not the path.

## Choosing where the sender runs

Hosted agents often run in a sandbox without your mailbox credentials or outbound SMTP.
In that case let the agent do steps 1 to 4 (discover, ingest, validate, export) and run
`scripts/hl_send.sh` on your own laptop, then give the results back (steps 5 to 8). If the
agent runs locally (Claude Code, Codex CLI, Antigravity on your machine), it can do the
whole loop on one machine.

## Scheduling

The reference schedule is Monday, Wednesday and Friday at midday. Use your agent's own
scheduler if it has one, or plain cron on the machine that runs the agent CLI:

```cron
# m  h  dom mon dow   command
0   12  *   *   1,3,5 cd ~/hire-lite && <your agent CLI> "Run one Hire Lite session per AGENTS.md" >> run.log 2>&1
```
