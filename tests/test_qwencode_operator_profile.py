from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVOKE = ROOT / "scripts" / "invoke-qwencode-hand.sh"
PROFILE = ROOT / "config" / "qwencode" / "server-operator-profile.md"
QWEN_MEMORY = ROOT / "QWEN.md"


def make_fake_qwen(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-qwen"
    fake.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
prompt=""
session_id=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)
      shift
      prompt="$1"
      ;;
    --session-id)
      shift
      session_id="$1"
      ;;
  esac
  shift
done
if [[ "${QWEN_FAKE_PRINT_SESSION_ID:-0}" == "1" ]]; then
  printf '%s\\n' "$session_id"
  exit 0
fi
if [[ -n "$prompt" ]]; then
  printf '%s\\n' "$prompt"
  exit 0
fi
printf 'missing prompt\\n' >&2
exit 2
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def run_invoke(fake_qwen: Path, message: str, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QWENCODE_BIN": str(fake_qwen),
        "QWENCODE_USE_PROXY": "0",
        "QWENCODE_OPENAI_LOGGING": "0",
    }
    env.update(env_overrides)
    return subprocess.run(
        [
            str(INVOKE),
            "--workdir",
            str(ROOT),
            "--message",
            message,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_wrapper_injects_server_operator_profile_by_default(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)

    result = run_invoke(fake_qwen, "Inspect the web-bat app.")

    assert result.returncode == 0, result.stderr
    normalized = " ".join(result.stdout.split())
    assert "OpenFang is the maestro" in normalized
    assert "source checkout, installed app tree, generated compose" in normalized
    assert "Never expose secrets" in normalized
    assert "Inspect the web-bat app." in normalized


def test_wrapper_can_disable_server_operator_profile(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)

    result = run_invoke(
        fake_qwen,
        "Say only RAW_PROMPT.",
        QWENCODE_INCLUDE_OPERATOR_PROFILE="0",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Say only RAW_PROMPT."


def test_wrapper_maps_label_session_id_to_stable_uuid(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)

    first = run_invoke(
        fake_qwen,
        "Inspect session handling.",
        QWENCODE_SESSION_ID="commit-push-verify",
        QWEN_FAKE_PRINT_SESSION_ID="1",
    )
    second = run_invoke(
        fake_qwen,
        "Inspect session handling again.",
        QWENCODE_SESSION_ID="commit-push-verify",
        QWEN_FAKE_PRINT_SESSION_ID="1",
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout
    assert first.stdout.strip() != "commit-push-verify"
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}",
        first.stdout.strip(),
    )


def test_qwen_native_memory_points_to_operator_profile() -> None:
    profile = PROFILE.read_text(encoding="utf-8")
    memory = QWEN_MEMORY.read_text(encoding="utf-8")

    for phrase in [
        "OpenFang is the maestro",
        "opencode-hand",
        "aider-hand",
        "Runtipi drift",
        "proof before claiming",
    ]:
        assert phrase in profile
        assert phrase in memory
