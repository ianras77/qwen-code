# Qwen Code in OpenFang

Qwen Code is the native coding executor behind `qwencode-hand`. Hermes routes
and supervises requests; OpenFang owns durable hand jobs, schedules, manifests,
dependency gates, and execution records.

## Installed path

- Source: `/data/apps/qwencode`
- CLI: `/data/apps/qwencode/bin/qwencode` (currently Qwen Code 0.21.3)
- OpenFang hand: `/data/apps/openfang/hands/qwencode/HAND.toml`
- Invocation wrapper: `/data/apps/qwencode/scripts/invoke-qwencode-hand.sh`
- Isolated Qwen home: `/data/apps/qwencode/state/qwen-home`
- Managed model catalog: `/data/apps/qwencode/config/qwencode/rassymind-models.json`
- Managed OpenFang skill: `config/qwencode/skills/openfang-handoff/SKILL.md`
- Operator context: `config/qwencode/server-operator-profile.md`

The CLI wrapper sources the RassyMind credential at runtime and exports it only
to the Qwen process. Never copy credentials into prompts, settings, reports, or
shell output. The setup reconciler atomically updates the managed RassyMind
entries in the isolated Qwen settings, preserves unrelated settings/providers,
and installs the OpenFang handoff skill. Run it with:

```bash
python3 /data/apps/qwencode/scripts/configure-qwencode-rassymind.py
python3 /data/apps/qwencode/scripts/configure-qwencode-rassymind.py --check
```

## Model routing

The OpenFang outer hand uses `rassy-fast` to dispatch tools and summarize
results. Qwen Code uses the selected route for the actual repository work:

| Route           | Use                                     | Context |
| --------------- | --------------------------------------- | ------: |
| `rassy-code`    | Main implementation and tool-heavy work |  65,536 |
| `rassy-mind`    | Deep architecture and long reviews      |  65,536 |
| `rassy-fast`    | Repo scouting and capacity fallback     |  65,536 |
| `rassy-quick`   | Small summaries and bounded tasks       |  65,536 |
| `rassy-utility` | Lightweight support work                |  32,768 |

Qwen Code's provider entries carry their own `contextWindowSize`, timeout, and
output budget. The provider layer is sealed, so a top-level setting or an
environment override does not fill missing fields on a listed provider model.
The reconciler keeps those per-route values explicit. For `rassy-code` and
`rassy-mind`, Qwen Code may fall back to `rassy-fast` on retryable capacity
responses (429/503/529). Set `QWENCODE_FALLBACK_MODELS` to override the fallback
list, or to an empty value to disable it.

## Native Qwen Code behavior

Normal hand runs do not pass `--bare`: Qwen Code can load the trusted repo's
`QWEN.md`, project skills, settings, and its built-in coding tools. The
server-operator profile is passed as a system prompt. The isolated Qwen home
contains no global MCP servers, so its baseline remains focused; a repository's
own MCP configuration is subject to Qwen Code's trust rules. Set
`QWENCODE_BARE=1` only for isolated diagnostics.

The default approval mode is `plan`. Use `auto-edit` only when the OpenFang job
explicitly authorizes a bounded patch; never use `yolo` as a workaround.
Normal runs do not enable OpenAI wire logging or debug output. Enable
`QWENCODE_OPENAI_LOGGING=1` only for a bounded diagnostic and protect the
resulting logs.

## Invoking the hand

Prefer a message file so shell quoting cannot change the request:

```bash
/data/apps/qwencode/scripts/invoke-qwencode-hand.sh \
  --workdir /path/to/repository \
  --model rassy-code \
  --approval-mode plan \
  --message-file /path/to/handoff.md
```

OpenFang's coding-job generator uses this wrapper for repository scouting,
selected-file edits, runtime preflight, and final review. Its runner preserves
the dependency graph and its report/ledger artifacts. Qwencode reports the
source or review evidence; runtime status is only marked proven when the
requested runtime surfaces were actually checked.

## Operational checks

```bash
/data/apps/qwencode/bin/qwencode --version
python3 /data/apps/qwencode/scripts/configure-qwencode-rassymind.py --check
```

Live qualification should use a small read-only task first, then a disposable
worktree task when verifying edit mode. Capture the requested model, any
capacity fallback, approval mode, final output, tool result, and Git diff.
