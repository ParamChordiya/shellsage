# ShellSage

> Plain English to shell commands, powered by Claude or Ollama.

[![PyPI](https://img.shields.io/pypi/v/shellsage-ai)](https://pypi.org/project/shellsage-ai/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/shellsage-ai)](https://pypi.org/project/shellsage-ai/)
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

## Chat Mode (Multi-Turn)

`shellsage chat` opens an interactive REPL where the full conversation — your
requests, the AI's responses, and actual command output — is remembered across
turns. Use it when you want to refine commands, build on previous results, or
have a back-and-forth with the AI.

```bash
shellsage chat
```

```
shellsage> list python files in this repo
  → ls **/*.py          [safe]   Run? y
  output: shellsage/agent.py, shellsage/chat.py ...

shellsage> now show only the ones modified in the last 7 days
  → find . -name "*.py" -mtime -7    [safe]   Run? y

shellsage> what was the output of the first command?
  The first command listed: shellsage/agent.py, shellsage/chat.py ...

shellsage> exit
```

Each turn automatically feeds the command output back to the AI, so follow-up
requests are always context-aware.

```bash
shellsage chat --dry-run          # show commands, never execute
shellsage chat --explain          # explain each command before prompting
shellsage chat --provider claude  # override provider for this session
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

## Safety System

ShellSage has a two-layer safety system:

### Hard Blocklist

The following commands are **always blocked** and can never run, regardless of
context:

- `rm -rf /`, `rm -rf /*`, `rm -rf ~`
- `dd if=/dev/zero`, `dd if=/dev/random`, `dd if=/dev/urandom`
- `mkfs`, `chmod -R 777 /`
- Fork bombs: `:(){ :|:& };:`
- Piping untrusted URLs into a shell: `curl | bash`, `wget -O- | sh`

### Danger Levels

Each proposed command is shown with a color-coded panel:

| Level | Color | Indicator |
|-------|-------|-----------|
| safe | Green | 🟢 |
| caution | Yellow | 🟡 |
| destructive | Red | 🔴 |

You always see the command and its danger level **before** being asked to run
it. Press **`e`** at the confirmation prompt for a detailed token-by-token
explanation.

---

## Switching Providers

```bash
shellsage config
```

This re-runs the interactive setup wizard where you can switch between Claude
and Ollama, change models, update your API key, and adjust the execution mode.

---

## How It Works

1. ShellSage detects your OS, shell, working directory, and installed tools.
2. It sends your English intent to the configured LLM with a structured prompt.
3. The LLM responds with a JSON plan containing one or more shell commands.
4. ShellSage validates each command against the safety blocklist.
5. You confirm (or explain, or skip) each command before it runs.
6. If a command fails, ShellSage automatically attempts to self-correct using
   the error output.
7. In chat mode, every exchange (including command output) is fed back into the
   conversation so follow-up requests are context-aware.

---

## Changelog

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
