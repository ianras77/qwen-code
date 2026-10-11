#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$root/scripts/configure-qwencode-rassymind.py" --quiet

grep -F 'export OPENAI_MODEL="${QWENCODE_OPENAI_MODEL:-rassy-code}"' "$root/bin/qwencode" >/dev/null
grep -F 'QWENCODE_OPENAI_MODEL:-rassy-code' "$root/scripts/invoke-qwencode-hand.sh" >/dev/null
grep -F 'RASSYMIND_API_KEY' "$root/bin/qwencode" >/dev/null
grep -F '/data/apps/rassymind/.env' "$root/bin/qwencode" >/dev/null
grep -F '"id": "rassy-utility"' "$root/state/qwen-home/settings.json" >/dev/null
grep -F '"id": "rassy-code"' "$root/state/qwen-home/settings.json" >/dev/null
grep -F '"id": "rassy-mind"' "$root/state/qwen-home/settings.json" >/dev/null
grep -F '"id": "rassy-quick"' "$root/state/qwen-home/settings.json" >/dev/null
grep -F '"contextWindowSize": 65536' "$root/state/qwen-home/settings.json" >/dev/null

printf '%s\n' 'QwenCode RassyMind alignment tests passed.'
