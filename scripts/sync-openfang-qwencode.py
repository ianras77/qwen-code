#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


QWENCODE_ROOT = Path("/data/apps/qwencode")
OPENFANG_ROOT = Path("/data/apps/openfang")
ENV_PATH = Path("/home/ianras/.openfang/.env")
API_BASE = "http://127.0.0.1:4200"


def write_if_changed(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def copy_manifest() -> bool:
    src = QWENCODE_ROOT / "openfang" / "qwencode" / "HAND.toml"
    dst = OPENFANG_ROOT / "hands" / "qwencode" / "HAND.toml"
    return write_if_changed(dst, src.read_text(encoding="utf-8"))


def patch_installer() -> bool:
    path = OPENFANG_ROOT / "scripts" / "install-coding-entrypoint-openfang.py"
    text = path.read_text(encoding="utf-8")
    entry = '    ROOT / "hands" / "qwencode" / "HAND.toml",\n'
    if entry in text:
        return False
    marker = '    ROOT / "hands" / "aider" / "HAND.toml",\n'
    if marker not in text:
        raise SystemExit(f"could not find HAND_MANIFESTS marker in {path}")
    text = text.replace(marker, marker + entry, 1)
    return write_if_changed(path, text)


def patch_codex_god() -> bool:
    path = OPENFANG_ROOT / "agents" / "codex-god.agent.toml"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'description = "OpenFang coordinator for Ian\'s server, routing work to opencode-hand and aider-hand while maintaining machine knowledge."':
        'description = "OpenFang coordinator for Ian\'s server, routing work to opencode-hand, aider-hand, and qwencode-hand while maintaining machine knowledge."',
        "route action through two hands:":
        "route action through three hands:",
        "- aider-hand: selected-file source editing, repo-map questions, ask/code/architect loops, and narrow implementation work.\n":
        "- aider-hand: selected-file source editing, repo-map questions, ask/code/architect loops, and narrow implementation work.\n- qwencode-hand: Qwen Code repo scouting, contained patch trials in worktrees, and independent pre-ship review.\n",
        "Decide whether the task needs opencode-hand, aider-hand, both in parallel preflight, or only a direct answer.":
        "Decide whether the task needs opencode-hand, aider-hand, qwencode-hand, paired preflight, or only a direct answer.",
        "- Source-only selected-file edits: use aider-hand.\n":
        "- Source-only selected-file edits: use aider-hand.\n- Broad repo scouting, patch trial, or independent pre-ship review: use qwencode-hand.\n",
        "Aider is a first-class source expert: selected-file source edits, repo-map reasoning, tight diffs, and source verification notes.\n":
        "Aider is a first-class source expert: selected-file source edits, repo-map reasoning, tight diffs, and source verification notes.\n- Qwencode is a first-class Qwen Code expert: broad repo scanning, alternate patch attempts, and independent ship/hold review.\n",
    }
    changed = False
    for old, new in replacements.items():
        if old in text and new not in text:
            text = text.replace(old, new, 1)
            changed = True
    if not changed:
        return False
    return write_if_changed(path, text)


def load_api_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "OPENFANG_API_KEY":
            return value.strip().strip('"').strip("'")
    raise SystemExit(f"OPENFANG_API_KEY not found in {ENV_PATH}")


def api_json(method: str, path: str, api_key: str, body: dict | None = None) -> dict | list:
    data = None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} failed: HTTP {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


def active_hand_ids(api_key: str) -> set[str]:
    data = api_json("GET", "/api/hands/active", api_key)
    rows = data.get("instances", []) if isinstance(data, dict) else []
    return {str(row.get("hand_id")) for row in rows if row.get("hand_id")}


def sync_runtime() -> None:
    subprocess.run(
        ["python3", str(OPENFANG_ROOT / "scripts" / "install-coding-entrypoint-openfang.py")],
        check=True,
    )
    api_key = load_api_key()
    if "qwencode" not in active_hand_ids(api_key):
        raise SystemExit("qwencode hand was not active after OpenFang installer ran")


def main() -> int:
    changed = {
        "manifest": copy_manifest(),
        "installer": patch_installer(),
        "codex_god": patch_codex_god(),
    }
    sync_runtime()
    for key, value in changed.items():
        print(f"{key}={'changed' if value else 'unchanged'}")
    print("openfang_qwencode=active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
