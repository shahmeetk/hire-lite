# Sender setup

The sender sends `outbox.jsonl` from your own mailbox and then checks that mailbox for
bounces. It can run on the agent machine or on a separate laptop.

## 1. Mailbox credentials

Use an app password, not your main password. For Gmail: enable 2-step verification,
then create an app password in your Google account security settings. Other providers:
set `sender.smtp_host`, `smtp_port`, `security` and `imap_host` in `config.yaml`.

Store the password in the OS keychain (recommended):

```bash
pip install keyring
python3 -m keyring set hire-lite-smtp you@example.com   # service name = sender.keyring_service
```

On macOS without `keyring`, the built-in Keychain also works:

```bash
security add-generic-password -s hire-lite-smtp -a you@example.com -w
```

Or set an environment variable (name from `sender.password_env`, default
`HL_SMTP_PASSWORD`), for example in a git-ignored `.env` file. Lookup order: env var,
`keyring`, macOS `security`.

## 2. Files on the sender machine

```
hire-lite/            # a clone of this repo
  config.yaml         # your profile + sender settings (git-ignored)
  templates/email.txt # edit once; fixed for every send
  resume.pdf          # your fixed resume (git-ignored), listed in sender.attachments
  outbox.jsonl        # copied from the agent machine each run
```

Check it with `python3 hl.py doctor`.

## 3. Preview, then send

```bash
bash scripts/hl_send.sh --dry-run      # renders results/preview_<ts>/*.eml, sends nothing
bash scripts/hl_send.sh 20             # send at most 20, wait, check bounces
```

The script prints three lines; the last names `results/results_<ts>.jsonl` and
`results/bounces_<ts>.txt`. Copy both back to the agent machine (scp, a synced folder,
or your agent's file-transfer feature) and run `mark-sent` / `mark-bounced` there.

## Safety limits

- `caps.send_max_per_run` and `caps.send_daily_max` (counted in `sent_register.txt`).
- `caps.send_delay_seconds` between messages.
- The resend guard refuses an address + url pair that was already sent from this machine.
- A real send refuses to start if an attachment is missing.
- `check-bounces` opens the mailbox read-only and never deletes or moves mail.
