# ShellSage

> Plain English to shell commands, powered by Claude or Ollama.

[![PyPI](https://img.shields.io/pypi/v/shellsage-ai)](https://pypi.org/project/shellsage-ai/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/shellsage-ai)](https://pypi.org/project/shellsage-ai/)
[![CI](https://github.com/ParamChordiya/shellsage/actions/workflows/ci.yml/badge.svg)](https://github.com/ParamChordiya/shellsage/actions/workflows/ci.yml)
![Claude API](https://img.shields.io/badge/Claude-API-orange?logo=anthropic)
![Ollama](https://img.shields.io/badge/Ollama-local-blue)
![Offline Capable](https://img.shields.io/badge/offline-capable-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

---

## Installation

```bash
pip install shellsage-ai
```

After installing, run the one-time setup:

```bash
shellsage init
```

---

## Quick Start

```bash
# Find all large files in your home directory
shellsage "find files larger than 100MB in my home directory"

# Create a new git branch and switch to it
shellsage "create a new git branch called feature/login and switch to it"

# Compress a folder
shellsage "compress the folder ./logs into a tar.gz archive"

# Kill a process on port 8080
shellsage "kill whatever process is running on port 8080"

# Bulk rename all .jpeg files to .jpg
shellsage "rename all .jpeg files in this folder to .jpg"
```

---

## Streaming Responses

ShellSage streams tokens as they arrive — no more waiting behind a silent spinner. You see the AI's reasoning in real time as it builds the command plan, and you can `Ctrl+C` early if it goes off track.

Streaming works automatically on both Claude and Ollama — no configuration needed.

---

## Chat Mode (Multi-Turn)

`shellsage chat` opens an interactive REPL where the full conversation — your requests, the AI's responses, and actual command output — is remembered across turns. Use it when you want to refine commands, build on previous results, or have a back-and-forth with the AI.

```bash
shellsage chat
```

```
Session: 20260506_143022_abc12345  •  Resume: shellsage chat --resume 20260506_143022_abc12345

shellsage> list python files in this repo
  → ls **/*.py          [safe]   Run? y
  output: shellsage/agent.py, shellsage/chat.py ...

shellsage> now show only the ones modified in the last 7 days
  → find . -name "*.py" -mtime -7    [safe]   Run? y

shellsage> what was the output of the first command?
  The first command listed: shellsage/agent.py, shellsage/chat.py ...

shellsage> exit
```

Each turn automatically feeds the command output back to the AI, so follow-up requests are always context-aware.

```bash
shellsage chat --dry-run          # show commands, never execute
shellsage chat --explain          # explain each command before prompting
shellsage chat --provider claude  # override provider for this session
```

### Session Persistence

Chat sessions are automatically saved to `~/.shellsage/sessions/` after every turn. Close the terminal, come back tomorrow — your context is still there.

```bash
# Resume the last session (or any session by ID)
shellsage chat --resume 20260506_143022_abc12345

# List all saved sessions
shellsage chat --list-sessions

# Delete a session
shellsage chat --delete-session 20260506_143022_abc12345
```

**Example `--list-sessions` output:**

```
┌──────────────────────────────┬─────────────────────┬──────────┬────────────────────────────────────┐
│ ID                           │ Last Updated        │ Messages │ Preview                            │
├──────────────────────────────┼─────────────────────┼──────────┼────────────────────────────────────┤
│ 20260506_143022_abc12345     │ 2026-05-06 15:45    │ 12       │ list python files in this repo     │
│ 20260505_091530_def67890     │ 2026-05-05 10:22    │ 6        │ debug the failing CI pipeline      │
└──────────────────────────────┴─────────────────────┴──────────┴────────────────────────────────────┘
```

---

## Ollama Setup (Local AI)

ShellSage can run entirely offline using [Ollama](https://ollama.com).

### 1. Install Ollama

| Platform | Command |
|----------|---------|
| macOS    | `brew install ollama` |
| Linux    | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Windows  | [https://ollama.com/download](https://ollama.com/download) |

### 2. Pull a model

```bash
ollama pull llama3.2        # recommended — fast and capable
ollama pull qwen2.5:3b      # lightweight, great for slower machines
ollama pull mistral         # most capable open model
```

### 3. Start the server

```bash
ollama serve
# macOS: starts automatically from the menu bar app
```

### 4. Verify

```bash
curl http://localhost:11434/api/tags
```

Then run `shellsage init` and choose **Ollama**.

---

## CLI Reference

```
Usage: shellsage [INTENT] [OPTIONS]
       shellsage COMMAND [OPTIONS]

Single-shot mode:
  shellsage "your intent"   Translate plain English into shell commands.

Options (single-shot):
  --dry-run           Show commands without executing them.
  --explain           Show per-token breakdown before prompting.
  --provider TEXT     Override configured provider: claude or ollama.
  --help              Show this message and exit.

Commands:
  chat      Start an interactive multi-turn chat session.
  init      Run the first-time setup wizard.
  config    Show current config / re-run the setup wizard.
  history   Print command history. Use --clear to wipe it.
```

### Examples

```bash
# Preview without running
shellsage "delete all .log files" --dry-run

# Get a detailed explanation of each command
shellsage "set up a Python virtual environment" --explain

# Override provider for this run
shellsage "list docker containers" --provider claude

# Start interactive chat mode
shellsage chat

# Resume a previous chat session
shellsage chat --resume 20260506_143022_abc12345

# List all saved sessions
shellsage chat --list-sessions

# Start chat in dry-run mode with a specific provider
shellsage chat --dry-run --provider ollama

# View saved command history
shellsage history

# Clear history
shellsage history --clear

# Reconfigure at any time
shellsage config
```

---

## Execution Modes

Choose how ShellSage handles command execution during `shellsage init` or
`shellsage config`:

| Mode | Behaviour |
|------|-----------|
| **Ask before each** (default) | Prompts `y / n / e` for every command, regardless of danger level. |
| **Auto-run safe, ask for others** | Safe commands run automatically; `caution` and `destructive` commands still require confirmation. |

The mode applies to both single-shot and chat sessions.

---

## Configuration

ShellSage stores its config in `~/.shellsage/config.toml`. You can edit it directly or use `shellsage config` to re-run the wizard.

Key settings in `~/.shellsage/config.toml`:

```toml
[provider]
type = "claude"            # or "ollama"
model = "claude-sonnet-4-6"

[preferences]
execution_mode = "ask_all" # or "auto_safe"
timeout = 30               # seconds; set to 0 for no timeout
max_retries = 3            # self-correction attempts on command failure
save_history = true
```

### Configurable Timeout

The default 30-second timeout is designed for quick commands. For long-running operations like `npm install`, `docker build`, or `terraform apply`, increase it:

```toml
[preferences]
timeout = 300   # 5 minutes
```

Or disable the timeout entirely:

```toml
[preferences]
timeout = 0     # no timeout
```

### Self-Correction Retries

When a command fails, ShellSage automatically generates a corrected command and retries. Each retry gets a richer prompt that includes all previous failed attempts:

```toml
[preferences]
max_retries = 3   # try up to 3 times (default)
```

---

## Safety System

ShellSage has a two-layer safety system designed to prevent accidental data loss.

### Hard Blocklist

The following patterns are **always blocked** and can never run, regardless of context:

- `rm -rf /`, `rm -rf /*`, `rm -rf ~` — root and home directory deletion
- `dd if=/dev/zero`, `dd if=/dev/random`, `dd if=/dev/urandom` — disk overwrite
- `mkfs`, `chmod -R 777 /` — filesystem operations
- `find / -delete`, `find / -exec rm` — recursive deletion via find
- `shred -u` — secure file deletion
- `history -c` — history wipe
- `chmod 000 /` — root lockout
- Fork bombs: `:(){ :|:& };:` and variants
- Piping untrusted content into a shell: `curl | bash`, `wget -O- | sh`, `| python`, `| perl`, etc.

**False-positive protection:** Commands wrapped in `echo "..."` or `printf "..."` are never blocked — printing a dangerous string is safe.

**Whitespace normalization:** Extra spaces and tabs in commands are collapsed before matching, closing the `rm  -rf /` whitespace-evasion bypass.

### Danger Levels

Each proposed command is shown with a color-coded panel:

| Level | Color | Indicator | Examples |
|-------|-------|-----------|---------|
| safe | Green | 🟢 | `ls`, `cat`, `echo` |
| caution | Yellow | 🟡 | `sudo`, `rm`, `mv`, `git push --force`, `kubectl delete` |
| destructive | Red | 🔴 | `rm -rf`, `dd`, `shutdown` |

You always see the command and its danger level **before** being asked to run it. Press **`e`** at the confirmation prompt for a detailed explanation.

---

## How It Works

1. ShellSage detects your OS, shell, working directory, and installed tools.
2. It sends your English intent to the configured LLM with a structured prompt.
3. The LLM response **streams in real time** — tokens appear as they arrive.
4. ShellSage validates each command against the safety blocklist.
5. You confirm (or explain, or skip) each command before it runs.
6. If a command fails, ShellSage automatically self-corrects using the error output, retrying up to `max_retries` times with progressively more context.
7. In chat mode, every exchange (including command output) is fed back into the conversation so follow-up requests are context-aware — and the session is saved so you can resume later.

---

## Switching Providers

```bash
shellsage config
```

This re-runs the interactive setup wizard where you can switch between Claude and Ollama, change models, update your API key, and adjust execution mode and timeout.

---

## Changelog

### v0.2.0 — Streaming, Sessions & Safety Hardening

- **Streaming responses** — tokens stream in real time for both Claude and Ollama; no more waiting behind a silent spinner. Uses Rich Live display, can be cancelled with `Ctrl+C`.
- **Session persistence** — `shellsage chat` sessions auto-save after every turn to `~/.shellsage/sessions/`. Resume with `--resume <id>`, list with `--list-sessions`, delete with `--delete-session`.
- **Configurable execution timeout** — set `preferences.timeout` in config (default: 30s, `0` = unlimited). Enables real-world workflows like `npm install`, `docker build`, and `terraform apply`.
- **Multi-attempt self-correction** — commands that fail are retried up to `preferences.max_retries` times (default: 3). Each retry gets a richer prompt that includes all previous failed attempts.
- **Safety hardening:**
  - Whitespace normalization before blocklist matching closes the extra-space evasion bypass.
  - Echo/printf false-positive fix: `echo "rm -rf /"` no longer triggers the blocklist.
  - 11 new blocklist patterns: `find -delete`, `find -exec rm`, `shred -u`, `history -c`, `chmod 000 /`, pipe-to-{`zsh`, `python`, `python3`, `perl`, `ruby`}, and fork bomb heuristic.
  - 7 new caution patterns: `git push --force`, `git push -f`, `git reset --hard`, `git clean -f`, `docker rm -f`, `docker rmi -f`, `kubectl delete`.
- **Bug fixes:**
  - Atomic history writes with advisory file locking (race condition fix for concurrent ShellSage processes).
  - API key redaction in Claude error messages (`sk-ant-*` tokens stripped before display).
  - Broader exception handling in chat REPL loop prevents conversation state corruption on unexpected errors.
- **Infrastructure:**
  - GitHub Actions CI across Python 3.10, 3.11, and 3.12 with version-sync gate.
  - 118 new tests (209 total, was 91) covering executor, history, config, and safety modules.

### v0.1.3 — Multi-Turn Chat Mode
- **New command: `shellsage chat`** — interactive REPL that accumulates the
  full conversation history (requests, AI responses, command output) across
  turns.
- Self-correction in chat mode uses the full conversation context, not just the
  last error.
- Blocked commands in chat mode no longer exit the session — they are reported
  and the REPL continues.
- Both Claude and Ollama providers now accept a `messages` array for multi-turn
  conversations.

### v0.1.2 — Execution Modes
- **New execution mode: `auto_safe`** — safe commands run automatically;
  `caution` and `destructive` commands still prompt for confirmation.
- Execution mode is configured during `shellsage init` / `shellsage config`
  and persists to `~/.shellsage/config.toml`.
- Default mode remains `ask_all` (prompt before every command) for safety.

### v0.1.1 — History & Config Fixes
- **Persistent history** — `shellsage history` now shows commands across
  sessions (stored in `~/.shellsage/history.json`, capped at 200 entries).
- **`shellsage history --clear`** — wipe all saved history.
- Fixed routing bug where `shellsage history` and `shellsage config` were
  incorrectly forwarded to the LLM as intents instead of being handled as
  subcommands.
- Config command now displays current settings in a formatted table before
  offering to re-run the wizard.

### v0.1.0 — Initial Release
- Single-shot mode: translate plain English to shell commands via Claude or
  Ollama.
- Two-layer safety system: hard blocklist + LLM-assigned danger levels
  (`safe` / `caution` / `destructive`).
- `--dry-run` flag to preview commands without executing.
- `--explain` flag for per-token command breakdown.
- `--provider` flag to override the configured provider per run.
- Automatic self-correction on command failure using the stderr output.
- First-time setup wizard (`shellsage init`).
- Context-aware prompts: OS, shell, working directory, and installed tools are
  injected into every request.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"` (package name on PyPI: `shellsage-ai`)
4. Run tests: `pytest tests/`
5. Submit a pull request.

Please keep pull requests focused on a single concern and include tests for new
functionality.

---

## License

MIT — see [LICENSE](LICENSE).
