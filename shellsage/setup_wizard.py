"""First-run interactive setup wizard for ShellSage."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

import shellsage.config as config

console = Console()

_OLLAMA_SETUP = """[bold]Install Ollama:[/bold]
  macOS:   [cyan]brew install ollama[/cyan]
  Linux:   [cyan]curl -fsSL https://ollama.com/install.sh | sh[/cyan]
  Windows: [cyan]https://ollama.com/download[/cyan]

[bold]Pull a model (choose one):[/bold]
  [cyan]ollama pull llama3.2[/cyan]        ← recommended
  [cyan]ollama pull qwen2.5:3b[/cyan]      ← lightweight
  [cyan]ollama pull mistral[/cyan]         ← most capable

[bold]Start the server:[/bold]
  [cyan]ollama serve[/cyan]
  (macOS: runs automatically from menu bar)"""


def run_wizard() -> None:
    """Run the interactive first-run setup wizard."""
    console.print(
        Panel(
            "[bold cyan]Welcome to ShellSage![/bold cyan]\n\n"
            "Turn plain English into shell commands, powered by AI.\n"
            "Let's get you set up in under a minute.",
            title="ShellSage Setup",
            border_style="cyan",
        )
    )

    # ---- Choose provider ------------------------------------------------
    console.print("\n[bold]Choose your AI provider:[/bold]")
    console.print("  [bold cyan][1][/bold cyan] Claude API  (cloud, best quality)")
    console.print("  [bold cyan][2][/bold cyan] Ollama      (local, free, private)\n")

    choice = Prompt.ask("Provider", choices=["1", "2"], default="2")
    provider_type = "claude" if choice == "1" else "ollama"

    cfg = config.load()
    cfg["provider"]["type"] = provider_type

    if provider_type == "claude":
        _configure_claude(cfg)
    else:
        _configure_ollama(cfg)

    # ---- History preference ---------------------------------------------
    save_history = Confirm.ask("\nRemember command history this session?", default=True)
    cfg["preferences"]["save_history"] = save_history

    # ---- Execution mode -------------------------------------------------
    console.print("\n[bold]How should ShellSage handle commands?[/bold]")
    console.print(
        "  [bold cyan][1][/bold cyan] Ask before every command "
        "[dim](default — safest)[/dim]"
    )
    console.print(
        "  [bold cyan][2][/bold cyan] Auto-run 🟢 safe commands, "
        "ask only for 🟡 caution and 🔴 destructive\n"
    )
    mode_choice = Prompt.ask("Execution mode", choices=["1", "2"], default="1")
    cfg["preferences"]["execution_mode"] = "ask_all" if mode_choice == "1" else "auto_safe"

    # ---- Persist config -------------------------------------------------
    config.save(cfg)

    console.print(
        Panel(
            "[bold green]Setup complete![/bold green]\n\n"
            "Run [bold cyan]shellsage \"your intent\"[/bold cyan] to get started.\n"
            "Run [bold cyan]shellsage --help[/bold cyan] to see all options.",
            title="Done",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# Provider-specific configuration helpers
# ---------------------------------------------------------------------------

def _configure_claude(cfg: dict) -> None:
    """Prompt for and validate an Anthropic API key."""
    console.print(
        "\n[bold]Claude API setup[/bold]\n"
        "Get your API key at [cyan]https://console.anthropic.com/[/cyan]"
    )

    api_key = Prompt.ask("ANTHROPIC_API_KEY", password=True)
    if not api_key.strip():
        console.print(
            Panel(
                "No API key provided. Run [bold cyan]shellsage init[/bold cyan] to try again.",
                border_style="red",
                title="Error",
            )
        )
        sys.exit(1)

    console.print("[dim]Validating API key...[/dim]")

    try:
        from shellsage.providers.claude import ClaudeProvider  # noqa: PLC0415
        import os  # noqa: PLC0415
        os.environ["ANTHROPIC_API_KEY"] = api_key
        provider = ClaudeProvider()
        if not provider.is_available():
            raise RuntimeError("API key validation failed.")
    except Exception as exc:
        console.print(
            Panel(
                f"[bold red]API key validation failed:[/bold red]\n{exc}\n\n"
                "Run [bold cyan]shellsage init[/bold cyan] to try again.",
                title="Error",
                border_style="red",
            )
        )
        sys.exit(1)

    config.save_api_key(api_key)
    cfg["provider"]["model"] = "claude-sonnet-4-6"
    console.print("[green]API key validated and saved.[/green]")


def _configure_ollama(cfg: dict) -> None:
    """Show Ollama setup instructions and validate connectivity."""
    console.print(
        Panel(
            _OLLAMA_SETUP,
            title="Ollama Setup",
            border_style="cyan",
        )
    )

    model = Prompt.ask(
        "Which model do you want to use?",
        default="llama3.2",
    ).strip() or "llama3.2"

    cfg["provider"]["model"] = model

    ollama_url = cfg["provider"].get("ollama_url", "http://localhost:11434")
    console.print(f"\n[dim]Checking Ollama at {ollama_url}...[/dim]")

    from shellsage.providers.ollama import OllamaProvider  # noqa: PLC0415

    provider = OllamaProvider(model=model, base_url=ollama_url)
    if not provider.is_available():
        console.print(
            Panel(
                f"[bold red]Ollama is not reachable at {ollama_url}[/bold red]\n\n"
                + _OLLAMA_SETUP
                + "\n\nAfter starting Ollama, run [bold cyan]shellsage init[/bold cyan] again.",
                title="Ollama not reachable",
                border_style="red",
            )
        )
        sys.exit(1)

    console.print(f"[green]Ollama is running. Using model: {model}[/green]")
