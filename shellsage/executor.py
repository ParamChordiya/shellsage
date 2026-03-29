"""Run shell commands via subprocess, respecting --dry-run mode."""

from __future__ import annotations

import subprocess
from typing import NamedTuple

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

_TIMEOUT = 30  # seconds


class ExecutionResult(NamedTuple):
    success: bool
    stdout: str
    stderr: str


def run(command: str, dry_run: bool = False) -> ExecutionResult:
    """Execute *command* in the user's shell.

    If *dry_run* is True the subprocess is never started; the command is
    simply printed and a success result is returned.
    """
    if dry_run:
        console.print(
            Panel(
                Text(command, style="bold cyan"),
                title="[bold]Dry Run[/bold]",
                border_style="cyan",
            )
        )
        return ExecutionResult(success=True, stdout="", stderr="")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        console.print(
            Panel(
                f"Command timed out after {_TIMEOUT} seconds:\n[bold]{command}[/bold]",
                title="Timeout",
                border_style="red",
            )
        )
        return ExecutionResult(success=False, stdout="", stderr="timeout")
    except Exception as exc:
        console.print(
            Panel(
                str(exc),
                title="Execution Error",
                border_style="red",
            )
        )
        return ExecutionResult(success=False, stdout="", stderr=str(exc))

    if result.stdout:
        console.print(
            Panel(
                result.stdout.rstrip(),
                title="Output",
                border_style="green",
            )
        )

    if result.stderr:
        console.print(
            Panel(
                result.stderr.rstrip(),
                title="stderr",
                border_style="yellow",
            )
        )

    success = result.returncode == 0
    return ExecutionResult(
        success=success,
        stdout=result.stdout,
        stderr=result.stderr,
    )
