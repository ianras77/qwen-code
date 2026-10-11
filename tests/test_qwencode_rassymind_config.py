from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "configure-qwencode-rassymind.py"


def load_module():
    spec = importlib.util.spec_from_file_location("configure_qwencode_rassymind", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconcile_registers_role_models_and_keeps_other_settings() -> None:
    configure = load_module()
    catalog = json.loads((ROOT / "config/qwencode/rassymind-models.json").read_text())
    initial = {
        "$version": 1,
        "theme": "dark",
        "modelProviders": {
            "openai": [
                {"id": "rassy-code", "name": "stale duplicate"},
                {"id": "custom-local", "name": "Keep me"},
            ],
            "anthropic": [{"id": "preserve-provider"}],
        },
    }

    result = configure.reconcile(initial, catalog)
    openai_models = result["modelProviders"]["openai"]
    by_id = {row["id"]: row for row in openai_models}

    assert set(by_id) == {"custom-local", "rassy-code", "rassy-mind", "rassy-fast", "rassy-quick", "rassy-utility"}
    assert by_id["custom-local"]["name"] == "Keep me"
    assert result["modelProviders"]["anthropic"] == [{"id": "preserve-provider"}]
    assert by_id["rassy-code"]["generationConfig"]["contextWindowSize"] == 65536
    assert by_id["rassy-code"]["generationConfig"]["samplingParams"]["max_tokens"] == 4096
    assert by_id["rassy-utility"]["generationConfig"]["contextWindowSize"] == 32768
    assert result["model"]["name"] == "rassy-code"


def test_runtime_reconciler_installs_models_skill_and_preserves_private_config(tmp_path: Path) -> None:
    home = tmp_path / "qwen-home"
    home.mkdir()
    settings = home / "settings.json"
    settings.write_text(json.dumps({"$version": 1, "mcpServers": {"private": {"url": "http://127.0.0.1"}}}))

    result = subprocess.run([sys.executable, str(SCRIPT), "--home", str(home)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    live = json.loads(settings.read_text())
    assert live["mcpServers"]["private"]["url"] == "http://127.0.0.1"
    assert (home / "skills/openfang-handoff/SKILL.md").is_file()

    check = subprocess.run([sys.executable, str(SCRIPT), "--home", str(home), "--check"], capture_output=True, text=True, check=False)
    assert check.returncode == 0, check.stdout + check.stderr
