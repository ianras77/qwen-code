# OpenFang Qwencode Hand

Qwencode is the local Qwen Code lane installed under `/data/apps/qwencode`.
OpenFang should treat it as a third coding peer next to Aider and OpenCode:
Aider stays the tight selected-file editor, OpenCode stays the host/runtime
operator, and Qwencode becomes the broad Qwen-native coding agent for repo
understanding, patch proposals, and independent review.

## Runtime

- Qwen Code source checkout: `/data/apps/qwencode`
- Standalone Qwen runtime: `/data/apps/qwencode/runtime/qwen-code`
- Local wrapper: `/data/apps/qwencode/bin/qwencode`
- OpenFang invocation wrapper: `/data/apps/qwencode/scripts/invoke-qwencode-hand.sh`
- Qwen native workspace memory: `/data/apps/qwencode/QWEN.md`
- Injected server-operator profile: `/data/apps/qwencode/config/qwencode/server-operator-profile.md`
- Default provider path: `http://127.0.0.1:8844/v1`
- Default model: `rassy-fast`
- Default API timeout: `120000` milliseconds via `QWEN_CODE_API_TIMEOUT_MS`
- Default OpenAI wire-log directory: `/data/apps/qwencode/state/openai-logs`
- Default compatibility proxy: enabled by `QWENCODE_USE_PROXY=1`
- Default proxy startup log directory: `/data/apps/qwencode/state/proxy-logs`

The wrapper sources `/data/apps/rassycodex/.env` at runtime and exports
OpenAI-compatible environment variables for Qwen Code. Do not copy API keys into
new docs, manifests, or command examples.

The OpenFang invocation wrapper uses Qwen Code's `--bare` mode by default so
starter handoffs stay explicit and fit the live local-model context budget.
Because `--bare` keeps implicit startup context tight, the wrapper explicitly
injects the server-operator profile into every hand prompt by default. Set
`QWENCODE_INCLUDE_OPERATOR_PROFILE=0` only for raw diagnostics.
The isolated Qwen home settings declare the local Rassy models for Qwen, but
this Qwen Code build still logs `max_tokens: 8000` for headless OpenAI calls.
The OpenFang wrapper therefore starts a tiny local OpenAI-compatible proxy that
caps `max_tokens`, forwards to RassyCodex, and normalizes streaming chunks.
Set `QWENCODE_USE_PROXY=0` to bypass it.
OpenFang wrapper calls keep local OpenAI wire logging on by default for
diagnostics; set `QWENCODE_OPENAI_LOGGING=0` to disable it.

Use `QWENCODE_MODEL=rassy-worker` for stronger short coding passes and
`QWENCODE_MODEL=rassy-codex` only for deeper runs where a longer startup and
response window is acceptable.

## Starter Use Cases

1. Qwen Scout

   OpenFang sends Qwencode a repo and asks for a read-only architectural pass:
   what the app does, likely edit points, missing tests, and whether the task
   should go to Aider, OpenCode, or a combined lane. This is the safest first
   routine because the default wrapper approval mode is `plan`.

   Example handoff:

   ```text
   Use qwencode-hand in plan mode on /data/apps/qwencode. Read the repo at a
   high level and return: purpose, package layout, likely edit points for an
   OpenFang hand integration, tests to run, and whether this should route next
   to Aider, OpenCode, or both. Do not edit files.
   ```

2. Patch Trial In A Worktree

   For a contained feature or bug fix, OpenFang creates a Git worktree and asks
   Qwencode to attempt the patch with `auto-edit`. Qwencode returns changed
   files and verification notes; Aider can then tighten the diff, and OpenCode
   can run the runtime proof.

   Example handoff:

   ```text
   Use qwencode-hand on the prepared worktree <worktree-path> with auto-edit
   approval. Implement only the requested small patch, list every changed file,
   and run the narrowest available verification. Leave deployment and live
   service proof for opencode-hand.
   ```

3. Independent Review Before Ship

   After Aider or OpenCode changes a repo, OpenFang asks Qwencode for an
   independent review against the original request. It should look for behavior
   gaps, missing tests, over-broad edits, and user-boundary violations, then
   return a ship/hold recommendation with concrete file references.

   Example handoff:

   ```text
   Use qwencode-hand in plan mode on <repo>. Review the current diff against
   this original request: <request>. Do not edit. Return findings first, then
   a ship/hold recommendation, exact file references, and any tests still
   missing.
   ```

## Verification Notes

- `bin/qwencode --version` returns `0.18.5`.
- The OpenFang invocation wrapper returned `QWENCODE_PROVIDER_CONFIG_OK` with
  the default `rassy-fast` model.
- Direct RassyCodex non-streaming and streaming probes returned
  `DIRECT_RASSY_FAST_OK` and `DIRECT_RASSY_STREAM_OK`.
- Some direct Qwen-to-RassyCodex headless attempts returned
  `APIConnectionError: fetch failed`; the wrapper keeps the compatibility proxy
  on by default to smooth that edge for OpenFang hand runs.
