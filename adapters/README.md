# Agent adapters

People start at [`docs/BOTS.md`](../docs/BOTS.md): install, first dry run, and how the bot
and the sender laptop split the work. The files here are what each product loads. They stay
short and point at [`AGENTS.md`](../AGENTS.md), which is the only copy of the run procedure.

| Agent | Files | How a person starts |
|---|---|---|
| Grok Bot | [`grok/ROUTINE_PROMPT.md`](grok/ROUTINE_PROMPT.md), [`grok/skills/hire-lite/SKILL.md`](grok/skills/hire-lite/SKILL.md) | Create a Bot, paste the routine, save the skill |
| Claude Code | [`CLAUDE.md`](../CLAUDE.md), [`.claude/commands/hire-lite-run.md`](../.claude/commands/hire-lite-run.md) | `claude`, then `/hire-lite-run` |
| Cursor | [`.cursor/rules/hire-lite.mdc`](../.cursor/rules/hire-lite.mdc), [`.cursor/skills/hire-lite/SKILL.md`](../.cursor/skills/hire-lite/SKILL.md) | Open the folder, type `/hire-lite` |
| ChatGPT / Codex | [`AGENTS.md`](../AGENTS.md), [`chatgpt/INSTRUCTIONS.md`](chatgpt/INSTRUCTIONS.md) | `codex` in this folder, or paste the instructions into chat |
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
