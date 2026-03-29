"""Typer CLI entrypoint for ShellSage."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

import shellsage.config as config
import shellsage.history as history

app = typer.Typer(
    name="shellsage",
    help="Plain English to shell commands, powered by Claude or Ollama.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _ensure_configured() -> None:
    """Run the setup wizard on first use (no config file present)."""
    if not config.config_exists():
        from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
        run_wizard()


@app.command(name="init")
def init_cmd() -> None:
    """Run the first-time setup wizard (or re-run to change settings)."""
    from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
    run_wizard()


@app.command(name="config")
def config_cmd() -> None:
    """Re-run the setup wizard to change your provider or preferences."""
    from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
    run_wizard()


@app.command(name="history")
def history_cmd() -> None:
    """Print this session's command history."""
    history.print_history()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    intent: Optional[str] = typer.Argument(
        None,
        help="Plain English description of what you want to do.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the command(s) without executing them.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show a per-token breakdown of each command before prompting.",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Override the configured provider: claude or ollama.",
        metavar="PROVIDER",
    ),
) -> None:
    """Translate INTENT into shell commands using AI."""
    if ctx.invoked_subcommand is not None:
        return

    if intent is None:
        console.print(ctx.get_help())
        raise typer.Exit()

    if provider and provider not in ("claude", "ollama"):
        console.print(
            f"[red]Unknown provider '[bold]{provider}[/bold]'. Use 'claude' or 'ollama'.[/red]"
        )
        raise typer.Exit(code=1)

    # First-run wizard
    _ensure_configured()

    # Configure session history from saved preference
    cfg = config.load()
    history.configure(config.get_save_history(cfg))

    from shellsage.agent import run as agent_run  # noqa: PLC0415

    try:
        agent_run(
            intent=intent,
            dry_run=dry_run,
            explain_flag=explain,
            provider_override=provider,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        raise typer.Exit()
    except Exception as exc:
        from rich.panel import Panel  # noqa: PLC0415
        console.print(Panel(str(exc), title="Error", border_style="red"))
        raise typer.Exit(code=1)
