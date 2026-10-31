#!/usr/bin/env bash
# End-to-end dry run on synthetic examples in a throwaway directory. Sends nothing,
# queries no DNS. Usage: bash scripts/demo.sh [workdir]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$(mktemp -d -t hire-lite-demo-XXXX)}"
mkdir -p "$WORK"
cp "$REPO/config.example.yaml" "$WORK/config.yaml"
cp -r "$REPO/templates" "$WORK/templates"
HL=(python3 "$REPO/hl.py" --home "$WORK")
step() { printf '\n$ hl %s\n' "$*"; "${HL[@]}" "$@"; }

echo "workdir: $WORK"
step ingest "$REPO/examples/harvest/20261102.jsonl"
step validate --skip-mx
step export --max 30
step send --dry-run

# Simulate delivery for the demo only: treat the dry-run results as sent.
RES="$(ls -t "$WORK"/results/results_*.jsonl | head -n 1)"
sed 's/"result": "dry-run"/"result": "sent"/' "$RES" > "$WORK/results/simulated_sent.jsonl"
step mark-sent "$WORK/results/simulated_sent.jsonl"

# Simulate one bounce, then queue the single allowed retry with a published corrected address.
printf 'hr@stark.example.net | 550 5.1.1 user unknown\n' > "$WORK/results/simulated_bounces.txt"
step mark-bounced "$WORK/results/simulated_bounces.txt"
step retry hr@stark.example.net careers@stark.example.net "careers page footer" --evidence "Contact careers@stark.example.net"
step validate --skip-mx
step report
step dashboard
