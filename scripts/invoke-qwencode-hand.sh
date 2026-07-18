#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
QWENCODE_BIN="${QWENCODE_BIN:-${ROOT}/bin/qwencode}"
WORKDIR="$PWD"
MESSAGE=""
MESSAGE_FILE=""
SESSION_ID="${QWENCODE_SESSION_ID:-}"
APPROVAL_MODE="${QWENCODE_APPROVAL_MODE:-plan}"
MODEL="${QWENCODE_MODEL:-${QWENCODE_OPENAI_MODEL:-rassy-fast}}"
TIMEOUT_SECONDS="${QWENCODE_HAND_TIMEOUT_SECONDS:-900}"
OUTPUT_FORMAT="${QWENCODE_OUTPUT_FORMAT:-text}"
ATTEMPTS="${QWENCODE_HAND_ATTEMPTS:-5}"
API_TIMEOUT_MS="${QWENCODE_API_TIMEOUT_MS:-120000}"
INCLUDE_OPERATOR_PROFILE="${QWENCODE_INCLUDE_OPERATOR_PROFILE:-1}"
OPERATOR_PROFILE="${QWENCODE_OPERATOR_PROFILE:-${ROOT}/config/qwencode/server-operator-profile.md}"
OPENAI_LOGGING="${QWENCODE_OPENAI_LOGGING:-1}"
OPENAI_LOGGING_DIR="${QWENCODE_OPENAI_LOGGING_DIR:-${ROOT}/state/openai-logs}"
USE_PROXY="${QWENCODE_USE_PROXY:-1}"
PROXY_MAX_TOKENS="${QWENCODE_PROXY_MAX_TOKENS:-512}"
PROXY_SCRIPT="${ROOT}/scripts/qwencode-openai-proxy.py"
PROXY_START_TIMEOUT_TENTHS="${QWENCODE_PROXY_START_TIMEOUT_TENTHS:-300}"
PROXY_LOG_DIR="${QWENCODE_PROXY_LOG_DIR:-${ROOT}/state/proxy-logs}"
RASSYCODEX_APP_ENV="${RASSYCODEX_APP_ENV:-/data/apps/rassycodex/.env}"
if [[ -r "$RASSYCODEX_APP_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$RASSYCODEX_APP_ENV"
  set +a
fi
RASSYCODEX_API_KEY="${RASSYCODEX_API_KEY:-${RASSYGPT_API_KEY:-}}"
RASSYCODEX_BASE_URL="${RASSYCODEX_BASE_URL:-${RASSYGPT_BASE_URL:-http://127.0.0.1:8844/v1}}"
if [[ -z "$RASSYCODEX_API_KEY" ]]; then
  printf 'RASSYCODEX_API_KEY is unavailable for Qwencode.\n' >&2
  exit 1
fi
declare -a EXTRA_ARGS=()

usage() {
  cat <<'USAGE'
Usage: invoke-qwencode-hand.sh [--workdir PATH] [--session-id UUID_OR_LABEL] [--approval-mode MODE] [--model MODEL] [--message TEXT|--message-file PATH] [-- EXTRA_QWEN_ARGS...]

Runs Qwen Code as OpenFang's Qwen-focused coding hand. The default approval mode
is plan, so OpenFang can use it for safe repo understanding and patch proposals.
The server-operator profile is injected by default; set
QWENCODE_INCLUDE_OPERATOR_PROFILE=0 to pass a raw prompt. Use auto-edit or yolo
only when the OpenFang job explicitly allows writes.
USAGE
}

normalize_session_id() {
  local raw="$1"
  if [[ "$raw" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    printf '%s\n' "$raw"
    return
  fi

  local hex
  hex="$(printf '%s' "openfang-qwencode:${raw}" | sha1sum | awk '{print $1}')"
  printf '%s-%s-5%s-8%s-%s\n' \
    "${hex:0:8}" \
    "${hex:8:4}" \
    "${hex:13:3}" \
    "${hex:17:3}" \
    "${hex:20:12}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workdir)
      WORKDIR="${2:?missing --workdir value}"
      shift 2
      ;;
    --session-id)
      SESSION_ID="${2:?missing --session-id value}"
      shift 2
      ;;
    --approval-mode)
      APPROVAL_MODE="${2:?missing --approval-mode value}"
      shift 2
      ;;
    --model)
      MODEL="${2:?missing --model value}"
      shift 2
      ;;
    --message)
      MESSAGE="${2:?missing --message value}"
      shift 2
      ;;
    --message-file)
      MESSAGE_FILE="${2:?missing --message-file value}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        EXTRA_ARGS+=("$1")
        shift
      done
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$APPROVAL_MODE" in
  plan|default|auto-edit|auto|yolo) ;;
  *)
    printf 'Unsupported approval mode: %s\n' "$APPROVAL_MODE" >&2
    usage >&2
    exit 2
    ;;
esac

if [[ -n "$MESSAGE" && -n "$MESSAGE_FILE" ]]; then
  printf 'Use either --message or --message-file, not both.\n' >&2
  exit 2
fi

TMP_MESSAGE=""
PROFILE_MESSAGE=""
PROXY_PORT_FILE=""
PROXY_PID=""
cleanup() {
  if [[ -n "$TMP_MESSAGE" && -f "$TMP_MESSAGE" ]]; then
    rm -f "$TMP_MESSAGE"
  fi
  if [[ -n "$PROFILE_MESSAGE" && -f "$PROFILE_MESSAGE" ]]; then
    rm -f "$PROFILE_MESSAGE"
  fi
  if [[ -n "$PROXY_PID" ]]; then
    kill "$PROXY_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$PROXY_PORT_FILE" && -f "$PROXY_PORT_FILE" ]]; then
    rm -f "$PROXY_PORT_FILE"
  fi
}
trap cleanup EXIT

if [[ -n "$MESSAGE" ]]; then
  TMP_MESSAGE="$(mktemp -t qwencode-hand-message.XXXXXX)"
  printf '%s\n' "$MESSAGE" >"$TMP_MESSAGE"
  MESSAGE_FILE="$TMP_MESSAGE"
fi

if [[ -z "$MESSAGE_FILE" ]]; then
  printf 'A message is required.\n' >&2
  usage >&2
  exit 2
fi

if [[ ! -d "$WORKDIR" ]]; then
  printf 'Workdir does not exist: %s\n' "$WORKDIR" >&2
  exit 2
fi

if [[ ! -x "$QWENCODE_BIN" ]]; then
  printf 'Qwencode wrapper not found or not executable: %s\n' "$QWENCODE_BIN" >&2
  exit 127
fi

if [[ "$INCLUDE_OPERATOR_PROFILE" != "0" ]]; then
  if [[ ! -r "$OPERATOR_PROFILE" ]]; then
    printf 'Qwencode operator profile is missing or unreadable: %s\n' "$OPERATOR_PROFILE" >&2
    exit 2
  fi
  PROFILE_MESSAGE="$(mktemp -t qwencode-hand-profile-message.XXXXXX)"
  {
    printf '<qwencode_server_operator_profile>\n'
    cat "$OPERATOR_PROFILE"
    printf '\n</qwencode_server_operator_profile>\n\n'
    printf '<openfang_task>\n'
    cat "$MESSAGE_FILE"
    printf '\n</openfang_task>\n'
  } >"$PROFILE_MESSAGE"
  MESSAGE_FILE="$PROFILE_MESSAGE"
fi

if [[ "$USE_PROXY" != "0" ]]; then
  if [[ ! -x "$PROXY_SCRIPT" ]]; then
    printf 'Qwencode OpenAI proxy not found or not executable: %s\n' "$PROXY_SCRIPT" >&2
    exit 127
  fi
  PROXY_PORT_FILE="$(mktemp -t qwencode-proxy-port.XXXXXX)"
  mkdir -p "$PROXY_LOG_DIR"
  PROXY_LOG="${PROXY_LOG_DIR}/proxy-$(date +%Y%m%dT%H%M%S).log"
  QWENCODE_PROXY_PORT_FILE="$PROXY_PORT_FILE" \
    QWENCODE_PROXY_UPSTREAM_BASE="$RASSYCODEX_BASE_URL" \
    QWENCODE_PROXY_API_KEY="$RASSYCODEX_API_KEY" \
    QWENCODE_PROXY_MAX_TOKENS="$PROXY_MAX_TOKENS" \
    "$PROXY_SCRIPT" >"$PROXY_LOG" 2>&1 &
  PROXY_PID="$!"
  for ((i = 0; i < PROXY_START_TIMEOUT_TENTHS; i++)); do
    if [[ -s "$PROXY_PORT_FILE" ]]; then
      break
    fi
    if ! kill -0 "$PROXY_PID" >/dev/null 2>&1; then
      printf 'Qwencode OpenAI proxy exited during startup. Log: %s\n' "$PROXY_LOG" >&2
      tail -n 20 "$PROXY_LOG" >&2 || true
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -s "$PROXY_PORT_FILE" ]]; then
    printf 'Qwencode OpenAI proxy did not start. Log: %s\n' "$PROXY_LOG" >&2
    tail -n 20 "$PROXY_LOG" >&2 || true
    exit 1
  fi
  export QWENCODE_OPENAI_BASE_URL="http://127.0.0.1:$(cat "$PROXY_PORT_FILE")/v1"
  export OPENAI_API_KEY="$RASSYCODEX_API_KEY"
fi

cmd=(
  timeout "$TIMEOUT_SECONDS" "$QWENCODE_BIN"
  --bare
  --model "$MODEL"
  --approval-mode "$APPROVAL_MODE"
  --output-format "$OUTPUT_FORMAT"
  --prompt "$(cat "$MESSAGE_FILE")"
)

if [[ "$OPENAI_LOGGING" != "0" ]]; then
  mkdir -p "$OPENAI_LOGGING_DIR"
  cmd+=(--openai-logging --openai-logging-dir "$OPENAI_LOGGING_DIR")
fi

if [[ -n "$SESSION_ID" ]]; then
  cmd+=(--session-id "$(normalize_session_id "$SESSION_ID")")
fi

cmd+=("${EXTRA_ARGS[@]}")

if ! [[ "$ATTEMPTS" =~ ^[0-9]+$ ]] || [[ "$ATTEMPTS" -lt 1 ]]; then
  printf 'QWENCODE_HAND_ATTEMPTS must be a positive integer.\n' >&2
  exit 2
fi

for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
  set +e
  output="$(cd "$WORKDIR" && DEBUG="${QWENCODE_DEBUG:-1}" QWEN_CODE_API_TIMEOUT_MS="$API_TIMEOUT_MS" "${cmd[@]}" 2>&1)"
  status=$?
  set -e

  if [[ "$status" -eq 0 && "$output" == *"[API Error:"* ]]; then
    status=1
  fi

  if [[ "$status" -eq 0 && "$output" != *"[API Error:"* ]]; then
    printf '%s\n' "$output"
    exit 0
  fi

  if [[ "$attempt" -lt "$ATTEMPTS" && "$output" == *"fetch failed"* ]]; then
    sleep $((attempt * 3))
    continue
  fi

  printf '%s\n' "$output"
  exit "$status"
done
