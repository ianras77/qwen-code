#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_CATALOG = ROOT / "config" / "qwencode" / "rassymind-models.json"
DEFAULT_HOME = ROOT / "state" / "qwen-home"
SKILL_SOURCE = ROOT / "config" / "qwencode" / "skills" / "openfang-handoff" / "SKILL.md"


def desired_model(row: dict, base_url: str) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "baseUrl": base_url,
        "envKey": "OPENAI_API_KEY",
        "generationConfig": {
            "timeout": row["timeout_ms"],
            "maxRetries": row["max_retries"],
            "contextWindowSize": row["context_window_size"],
            "samplingParams": {
                "temperature": 0.2,
                "max_tokens": row["max_output_tokens"],
            },
        },
    }


def reconcile(existing: dict, catalog: dict) -> dict:
    result = dict(existing)
    providers = dict(result.get("modelProviders") or {})
    auth_type = catalog["provider"]
    current = providers.get(auth_type, [])
    if not isinstance(current, list):
        current = []

    managed = {row["id"] for row in catalog["models"]}
    preserved = [row for row in current if not isinstance(row, dict) or row.get("id") not in managed]
    providers[auth_type] = preserved + [
        desired_model(row, catalog["base_url"]) for row in catalog["models"]
    ]
    result["modelProviders"] = providers

    default_row = next(row for row in catalog["models"] if row["id"] == catalog["default_model"])
    result["model"] = {
        **(result.get("model") if isinstance(result.get("model"), dict) else {}),
        "name": default_row["id"],
        "baseUrl": catalog["base_url"],
        "skipStartupContext": False,
        "generationConfig": desired_model(default_row, catalog["base_url"])["generationConfig"],
    }
    return result


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def sync_skill(home: Path, check: bool) -> bool:
    destination = home / "skills" / "openfang-handoff" / "SKILL.md"
    content = SKILL_SOURCE.read_text(encoding="utf-8")
    changed = not destination.exists() or destination.read_text(encoding="utf-8") != content
    if changed and not check:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Qwen Code's RassyMind model routes.")
    parser.add_argument("--home", type=Path, default=Path(os.environ.get("QWEN_HOME", DEFAULT_HOME)))
    parser.add_argument("--check", action="store_true", help="Report drift without writing settings.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    settings_path = args.home.expanduser() / "settings.json"
    existing = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {"$version": 1}
    catalog = json.loads(MODEL_CATALOG.read_text(encoding="utf-8"))
    updated = reconcile(existing, catalog)
    changed = updated != existing
    skill_changed = sync_skill(args.home.expanduser(), args.check)

    if changed and not args.check:
        write_atomic(settings_path, updated)
    if not args.quiet:
        state = "drift" if (changed or skill_changed) and args.check else "updated" if (changed or skill_changed) else "aligned"
        print(f"qwencode_rassymind_models={state} count={len(catalog['models'])} default={catalog['default_model']}")
        print(f"qwencode_openfang_skill={'drift' if skill_changed and args.check else 'updated' if skill_changed else 'aligned'}")
    return 1 if (changed or skill_changed) and args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
