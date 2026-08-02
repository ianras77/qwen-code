#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

grep -F 'export OPENAI_MODEL="${QWENCODE_OPENAI_MODEL:-rassy-code}"' "$root/bin/qwencode" >/dev/null
grep -F 'QWENCODE_OPENAI_MODEL:-rassy-code' "$root/scripts/invoke-qwencode-hand.sh" >/dev/null
grep -F 'RASSYMIND_API_KEY' "$root/bin/qwencode" >/dev/null
grep -F '/data/apps/rassymind/.env' "$root/bin/qwencode" >/dev/null

printf '%s\n' 'QwenCode RassyMind alignment tests passed.'
