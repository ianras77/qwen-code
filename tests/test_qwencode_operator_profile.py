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
system_prompt=""
session_id=""
all_args=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)
      shift
      prompt="$1"
      ;;
    --append-system-prompt)
      shift
      system_prompt="$1"
      ;;
    --session-id)
      shift
      session_id="$1"
      ;;
  esac
  shift
done
if [[ -n "${QWEN_FAKE_ARGS_FILE:-}" ]]; then
  printf '%s\\n' "${all_args[@]}" >"$QWEN_FAKE_ARGS_FILE"
fi
if [[ "${QWEN_FAKE_PRINT_SESSION_ID:-0}" == "1" ]]; then
  printf '%s\\n' "$session_id"
  exit 0
fi
if [[ -n "$prompt" ]]; then
  printf '<system>\\n%s\\n</system>\\n<prompt>\\n%s\\n</prompt>\\n' "$system_prompt" "$prompt"
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
        "QWENCODE_HAND_ATTEMPTS": "1",
    }
    env.update(env_overrides)
    return subprocess.run(
        [str(INVOKE), "--workdir", str(ROOT), "--message", message],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_wrapper_injects_operator_profile_as_system_context(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)
    args_path = tmp_path / "args.txt"
    result = run_invoke(fake_qwen, "Inspect the web-bat app.", QWEN_FAKE_ARGS_FILE=str(args_path))

    assert result.returncode == 0, result.stderr
    assert "OpenFang owns durable hand workflows" in result.stdout
    assert "Never print credentials" in result.stdout
    assert "Inspect the web-bat app." in result.stdout
    args = args_path.read_text(encoding="utf-8")
    assert "--append-system-prompt" in args
    assert "--bare" not in args


def test_wrapper_can_omit_operator_profile(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)
    result = run_invoke(fake_qwen, "Say only RAW_PROMPT.", QWENCODE_INCLUDE_OPERATOR_PROFILE="0")

    assert result.returncode == 0, result.stderr
    assert "Never print credentials" not in result.stdout
    assert "Say only RAW_PROMPT." in result.stdout


def test_wrapper_uses_coding_lane_with_capacity_fallback(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)
    args_path = tmp_path / "args.txt"
    result = run_invoke(fake_qwen, "Review a bounded code change.", QWEN_FAKE_ARGS_FILE=str(args_path))

    assert result.returncode == 0, result.stderr
    args = args_path.read_text(encoding="utf-8").splitlines()
    assert args[args.index("--model") + 1] == "rassy-code"
    assert args[args.index("--approval-mode") + 1] == "plan"
    assert args[args.index("--fallback-model") + 1] == "rassy-fast"
    assert "--bare" not in args


def test_wrapper_bare_mode_is_explicit_diagnostic_opt_in(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)
    args_path = tmp_path / "args.txt"
    result = run_invoke(fake_qwen, "Say only OK.", QWENCODE_BARE="1", QWEN_FAKE_ARGS_FILE=str(args_path))

    assert result.returncode == 0, result.stderr
    assert "--bare" in args_path.read_text(encoding="utf-8")


def test_wrapper_maps_label_session_id_to_stable_uuid(tmp_path: Path) -> None:
    fake_qwen = make_fake_qwen(tmp_path)
    first = run_invoke(fake_qwen, "Inspect session handling.", QWENCODE_SESSION_ID="commit-push-verify", QWEN_FAKE_PRINT_SESSION_ID="1")
    second = run_invoke(fake_qwen, "Inspect session handling again.", QWENCODE_SESSION_ID="commit-push-verify", QWEN_FAKE_PRINT_SESSION_ID="1")

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stdout.strip() != "commit-push-verify"
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}", first.stdout.strip())


def test_qwen_memory_and_operator_profile_align_on_roles() -> None:
    profile = PROFILE.read_text(encoding="utf-8")
    memory = QWEN_MEMORY.read_text(encoding="utf-8")

    for phrase in ["Hermes", "OpenFang", "Qwen Code", "Runtipi", "Never print credentials"]:
        assert phrase in profile
    for phrase in ["OpenFang owns live/runtime proof", "Hermes provides the supervised operator boundary"]:
        assert phrase in memory
