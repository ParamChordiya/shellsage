"""Session command history for ShellSage.

Entries are persisted to ~/.shellsage/history.json so that
`shellsage history` can display them even though each CLI invocation
is a separate process. The file is appended to during each run and
capped at MAX_ENTRIES to prevent unbounded growth.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from rich.console import Console
from rich.table import Table

console = Console()

_HISTORY_FILE = Path.home() / ".shellsage" / "history.json"
MAX_ENTRIES = 200

# In-memory list for the current process lifetime
_session_history: list[HistoryEntry] = []
_enabled: bool = True


class HistoryEntry(TypedDict):
    intent: str
    command: str
    success: bool
    timestamp: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure(enabled: bool) -> None:
    """Enable or disable history recording for this session."""
    global _enabled
    _enabled = enabled


def record(intent: str, command: str, success: bool) -> None:
    """Append an entry to the in-memory list and persist it to disk."""
    if not _enabled:
        return

    entry = HistoryEntry(
        intent=intent,
        command=command,
        success=success,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    _session_history.append(entry)
    _persist(entry)


def print_history() -> None:
    """Render persisted history as a Rich table."""
    entries = _load_all()
    if not entries:
        console.print("[dim]No history recorded yet.[/dim]")
        return

    table = Table(title="Command History", show_lines=True)
    table.add_column("Time", style="dim", width=19)
    table.add_column("Intent", style="cyan")
    table.add_column("Command", style="bold")
    table.add_column("Status", width=8)

    for entry in entries:
        status = "[green]OK[/green]" if entry["success"] else "[red]FAIL[/red]"
        table.add_row(
            entry["timestamp"],
            entry["intent"],
            entry["command"],
            status,
        )

    console.print(table)


def clear_history() -> None:
    """Delete the persisted history file."""
    if _HISTORY_FILE.exists():
        _HISTORY_FILE.unlink()
    _session_history.clear()
    console.print("[dim]History cleared.[/dim]")


def get_history() -> list[HistoryEntry]:
    """Return a copy of the current in-memory session history."""
    return list(_session_history)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _persist(entry: HistoryEntry) -> None:
    """Append *entry* to the history file, capping at MAX_ENTRIES."""
    try:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        entries = _load_all()
        entries.append(entry)
        # Keep only the most recent MAX_ENTRIES
        if len(entries) > MAX_ENTRIES:
            entries = entries[-MAX_ENTRIES:]
        _HISTORY_FILE.write_text(json.dumps(entries, indent=2))
    except Exception:
        # History persistence is best-effort — never crash the main flow
        pass


def _load_all() -> list[HistoryEntry]:
    """Read and return all persisted history entries."""
    if not _HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_HISTORY_FILE.read_text())
        return [HistoryEntry(**e) for e in data if isinstance(e, dict)]
    except Exception:
        return []
