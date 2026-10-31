# Use Hire Lite with Grok, Claude Code, Cursor, or ChatGPT

Hire Lite is the same program everywhere. The bot finds job posts that print a hiring email and runs the ledger. Your own mailbox sends the email. This page is the setup for a person who has never used the project.

You do not need all four bots. Pick the one you already have.

| If you already use | Install the bot | Then start a run with |
|---|---|---|
| [Grok Bot](https://x.ai/bot) | Desktop app, or the iOS / Android app | A new Bot named Hire Lite, then the prompt below |
| [Claude Code](https://code.claude.com/docs/en/quickstart) | `claude` in the terminal | `/hire-lite-run dry-run` |
| [Cursor](https://cursor.com) | The Cursor app, then open this folder | `/hire-lite` in the Agent chat |
| [ChatGPT](https://chatgpt.com) with Codex | `codex` in the terminal | The prompt below |

The rules the bot must follow live in [`AGENTS.md`](../AGENTS.md). You do not have to memorize them. Each setup below points the bot at that file.

## 1. Install Hire Lite (once)

You need Python 3.9 or newer. Check with `python3 --version`.

```bash
git clone https://github.com/shahmeetk/hire-lite.git
cd hire-lite
python3 -m pip install -r requirements.txt
python3 hl.py init
```

`init` creates `config.yaml`, `.env`, `harvest/`, and `results/` beside the code. Those files stay on your machine. They are git-ignored.

Then:

1. Open `config.yaml`. Set your name, the mailbox you send from, your headline, city, and notice period.
2. Put words for your home region in the **first** lane's `keywords`. Hire Lite sends that lane first, then fully remote, then hybrid.
3. Set `targets.roles` to the titles you want. Set `excluded_companies` and `excluded_locations` to places you will not apply.
4. Edit `templates/email.txt` once. The same letter goes out every time. Do not ask the bot to rewrite it per job.
5. Save your resume as `resume.pdf` in this folder.
6. Store the mailbox app password in the OS keychain (see [SENDER.md](SENDER.md)):

   ```bash
   python3 -m keyring set hire-lite-smtp you@example.com
   ```

7. Check the setup:

   ```bash
   python3 hl.py doctor
   bash scripts/demo.sh
   ```

`doctor` should say `doctor ok` after the placeholders are gone and `resume.pdf` exists. `demo.sh` runs the whole loop on fake companies and sends nothing. Open the `dashboard.html` it prints and click around. That is the same screen you will get from your own ledger.

## 2. What a run does

```text
you (or a schedule)
        |
        v
   the bot reads AGENTS.md
        |
        v
   one discovery pass  -->  harvest/YYYYMMDD.jsonl
        |
        v
   hl.py ingest  ->  validate  ->  export  ->  outbox.jsonl
        |
        +-- sender laptop offline? stop. leads stay queued.
        |
        v
   scripts/hl_send.sh     (your mailbox, your password)
        |
        v
   hl.py mark-sent  +  mark-bounced  +  report  +  dashboard
        |
        v
   one short note to you
```

The bot may do steps 1–4 on a cloud computer. Sending (step 5) should happen on the laptop where the mailbox password lives. Copy `outbox.jsonl` to that laptop, run `bash scripts/hl_send.sh`, and copy the two result files it names back. Then `mark-sent` and `mark-bounced`.

First real session: add `dry-run` so nothing is sent. Read one `.eml` preview in `results/preview_<time>/` before you allow a real send.

### Prompt you can paste into any of the bots

```text
Run one Hire Lite session. Read AGENTS.md and follow it.

- One discovery pass, at most caps.discovery_queries searches from config.yaml.
- Keep a lead only when the hiring email is printed in the post. Put that snippet in evidence. Never invent an address.
- Prefer my home region, then fully remote, then hybrid. Skip account walls, OTP, CAPTCHA, and Workday-style portals.
- Do not edit my resume or templates/email.txt.
- Run: python3 hl.py ingest, validate, export.
- This is a dry run: run bash scripts/hl_send.sh --dry-run and do not mark anything sent.
- Finish with python3 hl.py report only. Do not print the ledger. Tell me the report lines and whether anything is queued.
```

When a dry run looks right, drop the dry-run sentence and say you approve a real send.

## 3. Grok Bot

Grok Bot is the desktop and phone app with a cloud computer, skills, and routines. Install and sign-in are documented at [Get started](https://docs.x.ai/grok-bot/get-started).

1. Install the app from [x.ai/bot](https://x.ai/bot), or from the Grok Bot download row on the Cursor dashboard. On a phone, install Grok Bot from the App Store or Google Play. Sign in with the account your plan uses (Cursor, Grok, or X, depending on how you subscribe).
2. Choose **+** in the sidebar, then **Create a Bot**. Name it `Hire Lite`.
3. Send this as the first message so it keeps the job:

   ```text
   Your job is Hire Lite, an email-first job search. Clone https://github.com/shahmeetk/hire-lite and follow AGENTS.md on every run. Never guess a hiring email. Never edit the resume or the email template. Stop before sending unless I have approved a real send in this conversation. Remember this.
   ```

4. On the bot's computer, it needs your `config.yaml` and `resume.pdf`. Tell it your profile in chat and let it write `config.yaml` there, and upload the resume when it asks. Do not paste the mailbox password into chat. Leave sending on your laptop unless you want the bot to send and you are ready to enter the password in its secure sign-in form (the bot does not see that password).
5. Paste the [prompt above](#prompt-you-can-paste-into-any-of-the-bots) and let the first run finish as a dry run.
6. When the steps are right, tell the bot: `Save that process as a skill called Hire Lite.` The text in [`adapters/grok/skills/hire-lite/SKILL.md`](../adapters/grok/skills/hire-lite/SKILL.md) is the same procedure if you want to paste it.
7. Then set the schedule, in the bot's chat:

   ```text
   Every Monday, Wednesday, and Friday at 12:00, run the Hire Lite skill. If you cannot send mail, stop after export and tell me how many leads are queued. Do not contact anyone I have not already approved.
   ```

   Open the routine and read **When to run**. It should show that schedule in your time zone (Settings → Bot → Timezone). A new routine does not run at the moment you create it. Use **Test** only after a dry run has already looked right, because a test does the real work.

More detail on skills and routines: [Skills and routines](https://docs.x.ai/grok-bot/skills-routines-and-automations). A shorter copy of the routine prompt is in [`adapters/grok/ROUTINE_PROMPT.md`](../adapters/grok/ROUTINE_PROMPT.md).

## 4. Claude Code

Claude Code is Anthropic's terminal agent. In this repository it already has `CLAUDE.md` and a `/hire-lite-run` command.

1. Install it, then open a new terminal ([quickstart](https://code.claude.com/docs/en/quickstart)):

   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude --version
   ```

   On Windows PowerShell: `irm https://claude.ai/install.ps1 | iex`

2. From this folder:

   ```bash
   cd hire-lite
   claude
   ```

3. Claude Code loads `CLAUDE.md` by itself. Type:

   ```text
   /hire-lite-run dry-run
   ```

   `dry-run` previews mail and does not send. A number caps the batch, for example `/hire-lite-run dry-run 10`. The command file is [`.claude/commands/hire-lite-run.md`](../.claude/commands/hire-lite-run.md).

4. When the previews look like your letter, run `/hire-lite-run` without `dry-run`. Say yes only if this machine is the one with the mailbox password.

5. To repeat it on Monday, Wednesday, and Friday, cron is enough when the computer is on at noon:

   ```cron
   0 12 * * 1,3,5 cd $HOME/hire-lite && claude -p "Run one Hire Lite session following AGENTS.md. Stop after export if sending is not possible."
   ```

   Confirm the flag for a one-shot prompt in `claude --help`. Product flags change; the prompt does not.

## 5. Cursor

Cursor reads this repository's `AGENTS.md` and `.cursor/rules/hire-lite.mdc` whenever the folder is open.

1. Install Cursor from [cursor.com](https://cursor.com) and sign in.
2. **File → Open Folder** and choose the `hire-lite` directory. Do this after section 1 so `config.yaml` and `resume.pdf` are already there.
3. Open the Agent chat and type:

   ```text
   /hire-lite
   ```

   That skill is [`.cursor/skills/hire-lite/SKILL.md`](../.cursor/skills/hire-lite/SKILL.md). You can also paste the [shared prompt](#prompt-you-can-paste-into-any-of-the-bots).

4. The first time, ask for a dry run. Cursor on your computer can send, because it can run `scripts/hl_send.sh` and the keychain is on that computer. A cloud agent usually cannot see the keychain, so tell it to stop after `export` and send from the laptop yourself.

5. There is no separate scheduler inside the editor. Use the Grok Bot routine above if you want it to run while the laptop is closed, or the cron line from the Claude Code section if the computer is on at noon.

## 6. ChatGPT and Codex

Codex is the ChatGPT coding agent that can read this repo, run `hl.py`, and follow `AGENTS.md`. That is the setup that can actually drive the ledger. The ChatGPT website, by itself, can search the web, but it cannot keep your ledger unless you download the files and run the commands locally.

### Codex (recommended)

Install ([Codex CLI](https://learn.chatgpt.com/docs/codex/cli)), then sign in with your ChatGPT account:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
cd hire-lite
codex
```

On Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"`

Paste the [shared prompt](#prompt-you-can-paste-into-any-of-the-bots). Codex loads [`AGENTS.md`](../AGENTS.md) from the repository root on its own. `codex --help` shows how to pass a one-shot prompt if you want cron to start it.

### Chat in the browser

Use this when you want ChatGPT to help you find posts, and you will run the ledger yourself.

1. Start a chat that can search the web.
2. Paste the instructions in [`adapters/chatgpt/INSTRUCTIONS.md`](../adapters/chatgpt/INSTRUCTIONS.md).
3. Ask for a harvest file only: one JSON object per line, with `evidence` containing the printed email.
4. Save that file as `harvest/YYYYMMDD.jsonl` and run:

   ```bash
   python3 hl.py ingest harvest/YYYYMMDD.jsonl
   python3 hl.py validate
   python3 hl.py export
   bash scripts/hl_send.sh --dry-run
   ```

Custom GPTs are being retired (11 December 2026 for most workspaces) and new personal GPTs can no longer be created. Prefer Codex, or paste the instructions into a normal chat. If you still have a GPT you created earlier, its instructions field is the right place for that same text, with Code Interpreter turned on if you want it to run Python.

## 7. Read the result

After a run, the bot should send you at most ten lines from `python3 hl.py report`. Open the dashboard yourself when you want the picture:

```bash
python3 hl.py dashboard
```

That writes `dashboard.html`. Open it in a browser. It does not upload anything.

- Click a number, a bar, or a pipeline chip to filter.
- Click a row to see the evidence snippet and the status history.
- Press `/` to search and `Esc` to clear filters.

| Report word | What you do |
|---|---|
| `queued` | Validated leads are waiting. Run `bash scripts/hl_send.sh` when you are ready. |
| `bounced` | One new published address is allowed. Ask the bot to run `hl.py retry` only if it can point at the page where that address is printed. |
| `skipped` | A rule rejected the lead (free-mail, no email in the post, wrong location, duplicate). Leave it. |
| `dns-pending` | The MX check could not reach DNS. Run `python3 hl.py validate` again later. |

## 8. If it does not run

| What you see | What to do |
|---|---|
| `python3: command not found` | Install Python 3.9+ from [python.org](https://www.python.org/downloads/) and open a new terminal. |
| `doctor` complains about placeholders | `config.yaml` still says `Your Name` or `you@example.com`. |
| `doctor` complains about the resume | The file must be named `resume.pdf` in this folder, or change `sender.attachments`. |
| `no SMTP password` | Run the `keyring set` command in section 1, or set `HL_SMTP_PASSWORD` in `.env`. |
| `outbox empty` | Nothing validated. Read `python3 hl.py report` and the skip reasons. |
| The bot printed the whole ledger | Tell it to stop and to use `python3 hl.py report` only. The ledger has other people's email addresses. |
| The bot wants to guess an email | Refuse. `validate` will skip it, and you should not send it. |
