"""Run shell commands via subprocess, respecting --dry-run mode."""

from __future__ import annotations

import subprocess
from typing import NamedTuple, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class ExecutionResult(NamedTuple):
    success: bool
    stdout: str
    stderr: str


def run(command: str, dry_run: bool = False, timeout: Optional[int] = None) -> ExecutionResult:
    """Execute *command* in the user's shell.

    If *dry_run* is True the subprocess is never started; the command is
    simply printed and a success result is returned.

    *timeout* is the number of seconds to wait before killing the subprocess.
    Pass 0 for no timeout.  If omitted, the value from ~/.shellsage/config.toml
    is used (default: 30 seconds).
    """
    if timeout is None:
        from shellsage import config as _config  # noqa: PLC0415
        timeout = _config.get_timeout()

    # 0 means "no timeout" — translate to None for subprocess
    effective_timeout: Optional[int] = timeout if timeout > 0 else None

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
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        console.print(
            Panel(
                f"Command timed out after {timeout} seconds:\n[bold]{command}[/bold]",
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
