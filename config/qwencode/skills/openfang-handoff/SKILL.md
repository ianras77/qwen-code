---
name: openfang-handoff
description: Use for bounded source work, repository scouting, or independent review coordinated by OpenFang or Hermes.
---

# OpenFang and Hermes coding handoff

Use this skill when a task comes through `qwencode-hand`, an OpenFang coding-job manifest, or a Hermes handoff.

## Roles

- Hermes owns user interaction, identity, memory, routing, and approval policy.
- OpenFang owns durable jobs, hand manifests, schedules, dependency gates, the coding ledger, and final job status.
- Qwen Code is the coding executor. Use its native repository, editing, shell, skills, and MCP features that are explicitly available in the current workspace.
- RassyMind is the model gateway. Use `rassy-code` for implementation and tool-heavy source work, `rassy-fast` for scouting and capacity fallback, `rassy-mind` for deep architecture, `rassy-quick` for small summaries, and `rassy-utility` for lightweight support.

## Procedure

1. Read the OpenFang handoff and the repository's `QWEN.md`, `AGENTS.md`, and relevant project instructions before editing.
2. Record the starting Git status. Preserve existing user changes and distinguish them from this task.
3. Keep the task and file scope bounded. Follow the requested approval mode; `plan` is read-only, and `auto-edit` is only for an explicitly authorized edit job. Never switch to `yolo` to work around a blocked action.
4. Reproduce the reported behavior before changing code when possible. Prefer the smallest useful fix and the repository's normal commands.
5. Verify the changed behavior and report commands with their actual exit status. Do not describe a planned check as a passing check.
6. Return a compact handoff with outcome, changed files, verification evidence, report paths, and unresolved risks. OpenFang performs or coordinates live-service proof and records final state.

## Boundaries

- Never print credentials, raw environment files, bearer tokens, or private data.
- Do not call other coding harnesses from Qwen Code.
- Do not mutate services, Runtipi state, accounts, or persistent data as a side effect of source work. Keep deployment separate from repository edits.
- If the workspace has pre-existing changes, do not overwrite, reset, or stage them unless the task explicitly includes them.
