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

## Demo

![Demo](demo.gif)

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
Usage: shellsage [OPTIONS] [INTENT] COMMAND [ARGS]...

  Translate INTENT into shell commands using AI.

Arguments:
  INTENT  Plain English description of what you want to do.

Options:
  --dry-run           Show commands without executing them.
  --explain           Show per-token breakdown before prompting.
  --provider TEXT     Override configured provider: claude or ollama.
  --help              Show this message and exit.

Commands:
  init      Run the first-time setup wizard.
  config    Re-run the setup wizard to change settings.
  history   Print this session's command history.
```

### Examples

```bash
# Preview without running
shellsage "delete all .log files" --dry-run

# Get a detailed explanation of each command
shellsage "set up a Python virtual environment" --explain

# Override provider for this run
shellsage "list docker containers" --provider claude

# View commands run this session
shellsage history

# Reconfigure at any time
shellsage config
```

---

## Safety System

ShellSage has a two-layer safety system:

### Hard Blocklist

The following commands are **always blocked** and can never run, regardless of context:

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

You always see the command and its danger level **before** being asked to run it. You can also press **`e`** at the confirmation prompt to get a detailed token-by-token explanation.

---

## Switching Providers

```bash
shellsage config
```

This re-runs the interactive setup wizard where you can switch between Claude and Ollama, change models, and update your API key.

---

## How It Works

1. ShellSage detects your OS, shell, working directory, and installed tools.
2. It sends your English intent to the configured LLM with a structured prompt.
3. The LLM responds with a JSON plan containing one or more shell commands.
4. ShellSage validates each command against the safety blocklist.
5. You confirm (or explain, or skip) each command before it runs.
6. If a command fails, ShellSage automatically attempts to self-correct using the error output.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"` (package name on PyPI: `shellsage-ai`)
4. Run tests: `pytest tests/`
5. Submit a pull request.

Please keep pull requests focused on a single concern and include tests for new functionality.

---

## License

MIT — see [LICENSE](LICENSE).
