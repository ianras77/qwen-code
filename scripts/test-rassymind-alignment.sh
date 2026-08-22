#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

grep -F 'export OPENAI_MODEL="${QWENCODE_OPENAI_MODEL:-rassy-fast}"' "$root/bin/qwencode" >/dev/null
grep -F 'QWENCODE_OPENAI_MODEL:-rassy-fast' "$root/scripts/invoke-qwencode-hand.sh" >/dev/null
grep -F 'RASSYMIND_API_KEY' "$root/bin/qwencode" >/dev/null
grep -F '/data/apps/rassymind/.env' "$root/bin/qwencode" >/dev/null
grep -F '"id": "rassy-utility"' "$root/state/qwen-home/settings.json" >/dev/null
grep -F '"id": "rassy-code"' "$root/state/qwen-home/settings.json" >/dev/null

printf '%s\n' 'QwenCode RassyMind alignment tests passed.'
