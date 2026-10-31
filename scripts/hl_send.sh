#!/usr/bin/env bash
# Hire Lite sender: send outbox.jsonl, wait for fast bounces, scan the mailbox.
# Runs on the ledger machine or on a separate laptop with a clone of this repo.
#
#   bash scripts/hl_send.sh [MAX] [--dry-run]
#
# Reads config.yaml / outbox.jsonl from $HL_HOME (default: repo root). Prints 3 lines;
# the last one names the two files to copy back for `hl mark-sent` / `hl mark-bounced`.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export HL_HOME="${HL_HOME:-$REPO}"
MAX="${1:-}"
DRY="${2:-}"
[[ "$MAX" == "--dry-run" ]] && { DRY="--dry-run"; MAX=""; }
HL=(python3 "$REPO/hl.py" --home "$HL_HOME")

if [[ ! -s "$HL_HOME/outbox.jsonl" ]]; then echo "outbox empty"; exit 0; fi

SEND_OUT="$("${HL[@]}" send ${MAX:+--max "$MAX"} $DRY 2>&1)" || true
echo "$SEND_OUT" | tail -n 1
RESULTS="$(echo "$SEND_OUT" | grep -o 'results/results_[0-9_]*\.jsonl' | tail -n 1 || true)"

if [[ "$DRY" == "--dry-run" ]]; then
  echo "bounces skipped (dry run)"
  echo "${RESULTS:-no results file}"
  exit 0
fi

WAIT="$(python3 -c "import sys; sys.path.insert(0, '$REPO'); from hire_lite.config import load_config; print(load_config(home='$HL_HOME')['sender']['bounce_wait_seconds'])")"
sleep "$WAIT"  # let fast bounces arrive
BOUNCE_OUT="$("${HL[@]}" check-bounces 2>&1)" || BOUNCE_OUT="check-bounces failed: $BOUNCE_OUT"
echo "$BOUNCE_OUT" | tail -n 1
BOUNCES="$(echo "$BOUNCE_OUT" | grep -o 'results/bounces_[0-9_]*\.txt' | tail -n 1 || true)"
echo "${RESULTS:-no results file} ${BOUNCES:-no bounce file}"
