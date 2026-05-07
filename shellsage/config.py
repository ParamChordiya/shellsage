"""Read and write ShellSage configuration from ~/.shellsage/config.toml."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

_CONFIG_DIR = Path.home() / ".shellsage"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"
_ENV_FILE = _CONFIG_DIR / ".env"

_DEFAULTS: dict[str, Any] = {
    "provider": {
        "type": "ollama",
        "model": "llama3.2",
        "ollama_url": "http://localhost:11434",
    },
    "preferences": {
        "save_history": True,
        # "ask_all"  — prompt before every command (original behaviour)
        # "auto_safe" — auto-run safe commands, prompt only for caution/destructive
        "execution_mode": "ask_all",
        "timeout": 30,
        "max_retries": 3,
    },
}


def config_dir() -> Path:
    """Return the ~/.shellsage directory, creating it if necessary."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return _CONFIG_DIR


def config_exists() -> bool:
    """Return True if a config file is already present."""
    return _CONFIG_FILE.exists()


def load() -> dict[str, Any]:
    """Load config from disk, falling back to defaults for any missing keys."""
    if not _CONFIG_FILE.exists():
        return _deep_copy(_DEFAULTS)

    try:
        raw = tomllib.loads(_CONFIG_FILE.read_text())
    except Exception:
        # Corrupted file — reset to defaults
        return _deep_copy(_DEFAULTS)

    # Merge with defaults so missing keys always have a value
    merged = _deep_copy(_DEFAULTS)
    _deep_merge(merged, raw)
    return merged


def save(cfg: dict[str, Any]) -> None:
    """Persist the given config dict to ~/.shellsage/config.toml."""
    config_dir()
    _CONFIG_FILE.write_bytes(tomli_w.dumps(cfg).encode())


def save_api_key(api_key: str) -> None:
    """Write the Anthropic API key to ~/.shellsage/.env (never config.toml).

    Uses a write-to-temp-then-rename pattern so a crash during the write
    never leaves a partial or empty .env file.  chmod 600 is applied to the
    temp file *before* the rename so the key is never world-readable, even
    briefly.
    """
    config_dir()
    # Bug fix: the previous code wrote the key in-place then called chmod,
    # so a crash between write and chmod left the key world-readable.
    # A crash during write itself left an empty or truncated .env file.
    # Fix: fchmod the fd *before* writing, then rename atomically.
    tmp_fd, tmp_path = tempfile.mkstemp(dir=_CONFIG_DIR, suffix=".tmp")
    try:
        os.fchmod(tmp_fd, 0o600)
        with os.fdopen(tmp_fd, "w") as f:
            f.write(f'ANTHROPIC_API_KEY="{api_key}"\n')
        os.replace(tmp_path, _ENV_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_provider_type(cfg: dict[str, Any] | None = None) -> str:
    if cfg is None:
        cfg = load()
    return cfg.get("provider", {}).get("type", "ollama")


def get_provider_model(cfg: dict[str, Any] | None = None) -> str:
    if cfg is None:
        cfg = load()
    return cfg.get("provider", {}).get("model", "llama3.2")


def get_ollama_url(cfg: dict[str, Any] | None = None) -> str:
    if cfg is None:
        cfg = load()
    return cfg.get("provider", {}).get("ollama_url", "http://localhost:11434")


def get_save_history(cfg: dict[str, Any] | None = None) -> bool:
    if cfg is None:
        cfg = load()
    return bool(cfg.get("preferences", {}).get("save_history", True))


def get_execution_mode(cfg: dict[str, Any] | None = None) -> str:
    """Return 'ask_all' or 'auto_safe'."""
    if cfg is None:
        cfg = load()
    mode = cfg.get("preferences", {}).get("execution_mode", "ask_all")
    return mode if mode in ("ask_all", "auto_safe") else "ask_all"


def get_timeout(cfg: dict[str, Any] | None = None) -> int:
    """Return the command execution timeout in seconds (0 = no timeout)."""
    if cfg is None:
        cfg = load()
    value = cfg.get("preferences", {}).get("timeout", 30)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 30


def get_max_retries(cfg: dict[str, Any] | None = None) -> int:
    """Return the maximum number of self-correction attempts (default 3)."""
    if cfg is None:
        cfg = load()
    value = cfg.get("preferences", {}).get("max_retries", 3)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


def _deep_merge(base: dict, override: dict) -> None:
    """Merge *override* into *base* in-place, recursing into nested dicts."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
