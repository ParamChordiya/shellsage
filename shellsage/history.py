"""In-memory session history for ShellSage commands."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from rich.console import Console
from rich.table import Table

console = Console()


class HistoryEntry(TypedDict):
    intent: str
    command: str
    success: bool
    timestamp: str


_session_history: list[HistoryEntry] = []
_enabled: bool = True


def configure(enabled: bool) -> None:
    """Enable or disable history recording for this session."""
    global _enabled
    _enabled = enabled


def record(intent: str, command: str, success: bool) -> None:
    """Append an entry to the in-memory session history if enabled."""
    if not _enabled:
        return
    _session_history.append(
        HistoryEntry(
            intent=intent,
            command=command,
            success=success,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
    )


def print_history() -> None:
    """Render the session history as a Rich table."""
    if not _session_history:
        console.print("[dim]No commands recorded this session.[/dim]")
        return

    table = Table(title="Session History", show_lines=True)
    table.add_column("Time", style="dim", width=10)
    table.add_column("Intent", style="cyan")
    table.add_column("Command", style="bold")
    table.add_column("Status", width=8)

    for entry in _session_history:
        status = "[green]OK[/green]" if entry["success"] else "[red]FAIL[/red]"
        table.add_row(
            entry["timestamp"],
            entry["intent"],
            entry["command"],
            status,
        )

    console.print(table)


def get_history() -> list[HistoryEntry]:
    """Return a copy of the current session history."""
    return list(_session_history)
