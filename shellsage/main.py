"""Typer CLI entrypoint for ShellSage."""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console

import shellsage.config as config
import shellsage.history as history

# Known subcommand names — used by the entry-point pre-router below.
_SUBCOMMANDS = frozenset({"init", "config", "history", "ask"})

app = typer.Typer(
    name="shellsage",
    help="Plain English to shell commands, powered by Claude or Ollama.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


# ---------------------------------------------------------------------------
# Entry point
#
# Click (which Typer wraps) parses a Group's own positional arguments BEFORE
# looking up subcommand names. That means having `intent` as a positional arg
# on the callback caused "shellsage history" to be consumed as intent="history"
# instead of routing to history_cmd.
#
# The fix: the callback has NO positional args. Instead this thin wrapper
# inspects sys.argv and injects the hidden "ask" subcommand name when the
# first token is not a known subcommand or option flag.
# ---------------------------------------------------------------------------

def main() -> None:
    """Package entry point — routes bare intents to the 'ask' command."""
    args = sys.argv[1:]
    if args and not args[0].startswith("-") and args[0] not in _SUBCOMMANDS:
        sys.argv = [sys.argv[0], "ask"] + args
    app()


# ---------------------------------------------------------------------------
# Callback — no positional args, just global options + help-when-empty guard
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def _callback(ctx: typer.Context) -> None:
    """Plain English to shell commands, powered by Claude or Ollama."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Core intent command (hidden — invoked via the pre-router above)
# ---------------------------------------------------------------------------

@app.command(name="ask", hidden=True)
def ask_cmd(
    intent: str = typer.Argument(..., help="Plain English description of what you want to do."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show commands without executing."),
    explain: bool = typer.Option(False, "--explain", help="Show per-token breakdown before prompting."),
    provider: Optional[str] = typer.Option(
        None, "--provider", metavar="PROVIDER",
        help="Override provider for this run: claude or ollama.",
    ),
) -> None:
    """Translate INTENT into shell commands using AI."""
    _run_agent(intent, dry_run, explain, provider)


# ---------------------------------------------------------------------------
# Named subcommands
# ---------------------------------------------------------------------------

@app.command(name="init")
def init_cmd() -> None:
    """Run the first-time setup wizard (or re-run to change settings)."""
    from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
    run_wizard()


@app.command(name="config")
def config_cmd() -> None:
    """Show current configuration and optionally re-run the setup wizard."""
    _show_current_config()
    if typer.confirm("\nRe-run setup wizard to change settings?", default=False):
        from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
        run_wizard()


@app.command(name="history")
def history_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all saved history."),
) -> None:
    """Print command history. Use --clear to wipe it."""
    if clear:
        history.clear_history()
    else:
        history.print_history()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ensure_configured() -> None:
    if not config.config_exists():
        from shellsage.setup_wizard import run_wizard  # noqa: PLC0415
        run_wizard()


def _run_agent(
    intent: str,
    dry_run: bool,
    explain: bool,
    provider: Optional[str],
) -> None:
    if provider and provider not in ("claude", "ollama"):
        console.print(
            f"[red]Unknown provider '[bold]{provider}[/bold]'. Use 'claude' or 'ollama'.[/red]"
        )
        raise typer.Exit(code=1)

    _ensure_configured()

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


def _show_current_config() -> None:
    from rich.table import Table  # noqa: PLC0415

    cfg = config.load()
    provider_type = config.get_provider_type(cfg)
    model = config.get_provider_model(cfg)
    ollama_url = config.get_ollama_url(cfg)
    save_hist = config.get_save_history(cfg)

    table = Table(title="Current Configuration", show_header=False, show_lines=True)
    table.add_column("Key", style="dim")
    table.add_column("Value", style="bold cyan")
    table.add_row("Provider", provider_type)
    table.add_row("Model", model)
    if provider_type == "ollama":
        table.add_row("Ollama URL", ollama_url)
    table.add_row("Save history", "yes" if save_hist else "no")
    table.add_row("Config file", str(config._CONFIG_FILE))
    console.print(table)
