"""Core agent loop: translate English intent into shell commands and execute them."""

from __future__ import annotations

import json
import sys
from typing import TypedDict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

import shellsage.config as config
import shellsage.history as history
from shellsage.context import ShellContext, get_context
from shellsage.executor import run as execute
from shellsage.providers.base import LLMProvider
from shellsage.safety import classify_danger, danger_color, danger_emoji, is_blocked

console = Console()


class Step(TypedDict):
    command: str
    explanation: str
    danger_level: str


# ---------------------------------------------------------------------------
# System prompt factory
# ---------------------------------------------------------------------------

def _build_system_prompt(ctx: ShellContext) -> str:
    tools_str = ", ".join(ctx.tools) if ctx.tools else "standard POSIX tools"
    return f"""You are ShellSage, an expert shell command assistant.
The user is on {ctx.os_name} using {ctx.shell}.
Current directory: {ctx.cwd}
Installed tools detected: {tools_str}

When given a plain English task, respond ONLY with valid JSON in this exact format:
{{
  "steps": [
    {{
      "command": "shell command here",
      "explanation": "plain English explanation",
      "danger_level": "safe|caution|destructive"
    }}
  ]
}}

Rules:
- Use only commands available in the detected tools list
- Prefer safe, reversible approaches
- If a task requires multiple commands, return multiple steps
- Never include markdown, explanations outside the JSON, or any other text
- danger_level must be exactly one of: safe, caution, destructive"""


def _build_explain_prompt(command: str) -> str:
    return (
        f"Break down every token of this shell command and explain what each part does:\n\n"
        f"  {command}\n\n"
        "Give a clear, beginner-friendly breakdown. Use plain text, no JSON."
    )


def _build_correction_prompt(command: str, stderr: str) -> str:
    return (
        f"The command failed:\n\n"
        f"  {command}\n\n"
        f"Error output:\n{stderr}\n\n"
        "Please provide a corrected version. "
        "Respond ONLY with valid JSON in the same format as before."
    )


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _parse_steps(raw: str) -> list[Step]:
    """Parse the LLM response into a list of Step dicts.

    Strips markdown fences if present, then attempts json.loads().
    """
    text = raw.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        )

    data = json.loads(text)
    steps: list[Step] = []
    for item in data.get("steps", []):
        steps.append(
            Step(
                command=str(item.get("command", "")),
                explanation=str(item.get("explanation", "")),
                danger_level=str(item.get("danger_level", "safe")),
            )
        )
    return steps


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def _make_provider(provider_override: str | None = None) -> LLMProvider:
    cfg = config.load()
    provider_type = provider_override or config.get_provider_type(cfg)
    model = config.get_provider_model(cfg)

    if provider_type == "claude":
        from shellsage.providers.claude import ClaudeProvider  # noqa: PLC0415
        return ClaudeProvider(model=model)

    from shellsage.providers.ollama import OllamaProvider  # noqa: PLC0415
    ollama_url = config.get_ollama_url(cfg)
    return OllamaProvider(model=model, base_url=ollama_url)


# ---------------------------------------------------------------------------
# LLM call with spinner
# ---------------------------------------------------------------------------

def _call_llm(provider: LLMProvider, system: str, user: str, label: str = "Thinking") -> str:
    """Call the provider inside a Rich live spinner and return the raw text."""
    result_holder: list[str] = []
    error_holder: list[Exception] = []

    spinner = Spinner("dots", text=f"[dim]{label}...[/dim]")
    with Live(spinner, console=console, refresh_per_second=10):
        try:
            result_holder.append(provider.complete(system, user))
        except Exception as exc:
            error_holder.append(exc)

    if error_holder:
        raise error_holder[0]
    return result_holder[0]


# ---------------------------------------------------------------------------
# Step rendering
# ---------------------------------------------------------------------------

def _render_step(step: Step, index: int, total: int) -> None:
    effective_level = classify_danger(step["command"], step["danger_level"])
    color = danger_color(effective_level)
    emoji = danger_emoji(effective_level)

    subtitle = f"Step {index} of {total}" if total > 1 else None
    body = (
        f"[bold]{step['command']}[/bold]\n\n"
        f"[dim]{step['explanation']}[/dim]\n\n"
        f"{emoji} [bold]{effective_level.upper()}[/bold]"
    )
    console.print(
        Panel(
            body,
            title="[bold]Proposed Command[/bold]",
            subtitle=subtitle,
            border_style=color,
        )
    )


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

def run(
    intent: str,
    dry_run: bool = False,
    explain_flag: bool = False,
    provider_override: str | None = None,
) -> None:
    """Translate *intent* into shell commands and optionally execute them."""
    ctx = get_context()
    system_prompt = _build_system_prompt(ctx)

    try:
        provider = _make_provider(provider_override)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Error", border_style="red"))
        sys.exit(1)

    # ---- First LLM call -------------------------------------------------
    try:
        raw = _call_llm(provider, system_prompt, intent)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Error", border_style="red"))
        sys.exit(1)

    steps = _parse_with_retry(provider, system_prompt, intent, raw)
    if not steps:
        console.print(Panel("No commands were generated.", title="Error", border_style="red"))
        sys.exit(1)

    total = len(steps)
    execution_mode = config.get_execution_mode()

    # When auto_safe mode is active and the plan has multiple steps, show a
    # summary so the user knows what will run automatically vs what needs approval.
    if execution_mode == "auto_safe" and total > 1:
        _render_plan_summary(steps, total)

    # ---- Process each step ----------------------------------------------
    for idx, step in enumerate(steps, start=1):
        _process_step(
            step=step,
            idx=idx,
            total=total,
            intent=intent,
            dry_run=dry_run,
            explain_flag=explain_flag,
            provider=provider,
            system_prompt=system_prompt,
            execution_mode=execution_mode,
        )


# ---------------------------------------------------------------------------
# Step processing
# ---------------------------------------------------------------------------

def _process_step(
    *,
    step: Step,
    idx: int,
    total: int,
    intent: str,
    dry_run: bool,
    explain_flag: bool,
    provider: LLMProvider,
    system_prompt: str,
    execution_mode: str = "ask_all",
) -> None:
    """Handle one step: show, optionally auto-run, prompt, explain, self-correct.

    execution_mode:
      "ask_all"   — always prompt before running (original behaviour)
      "auto_safe" — run safe commands automatically; prompt for caution/destructive
    """
    # Blocklist check — always enforced regardless of execution mode
    if is_blocked(step["command"]):
        console.print(
            Panel(
                f"[bold red]{step['command']}[/bold red]\n\n"
                "This command matches the hard blocklist and cannot be run.",
                title="Blocked",
                border_style="red",
            )
        )
        sys.exit(1)

    effective_level = classify_danger(step["command"], step["danger_level"])
    auto_run = execution_mode == "auto_safe" and effective_level == "safe"

    _render_step(step, idx, total)

    if auto_run:
        console.print("[dim]Auto-running (safe command)...[/dim]")
        result = execute(step["command"], dry_run=dry_run)
        history.record(intent=intent, command=step["command"], success=result.success)
        if result.success or dry_run:
            return
        # Even auto-run steps self-correct on failure
        _self_correct(
            step=step, idx=idx, total=total, intent=intent,
            stderr=result.stderr, dry_run=dry_run, provider=provider,
            system_prompt=system_prompt, execution_mode=execution_mode,
        )
        return

    # --explain auto-explains before prompting
    if explain_flag:
        _show_explanation(provider, step["command"])

    # Manual prompt
    while True:
        answer = Prompt.ask(
            "[bold]Run this?[/bold] [dim](y / n / e to explain)[/dim]",
            choices=["y", "n", "e"],
            default="y",
        ).lower()

        if answer == "n":
            console.print("[dim]Skipped.[/dim]")
            return

        if answer == "e":
            _show_explanation(provider, step["command"])
            continue

        # answer == "y"
        result = execute(step["command"], dry_run=dry_run)
        history.record(intent=intent, command=step["command"], success=result.success)

        if result.success or dry_run:
            return

        _self_correct(
            step=step, idx=idx, total=total, intent=intent,
            stderr=result.stderr, dry_run=dry_run, provider=provider,
            system_prompt=system_prompt, execution_mode=execution_mode,
        )
        return


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _self_correct(
    *,
    step: Step,
    idx: int,
    total: int,
    intent: str,
    stderr: str,
    dry_run: bool,
    provider: LLMProvider,
    system_prompt: str,
    execution_mode: str,
) -> None:
    """Ask the LLM to fix a failed command, then re-process the corrected step."""
    console.print(
        Panel(
            stderr or "(no stderr output)",
            title="Command failed — attempting self-correction",
            border_style="yellow",
        )
    )
    try:
        correction_prompt = _build_correction_prompt(step["command"], stderr)
        raw_correction = _call_llm(
            provider, system_prompt, correction_prompt, label="Correcting"
        )
        corrected_steps = _parse_with_retry(
            provider, system_prompt, correction_prompt, raw_correction
        )
    except Exception as exc:
        console.print(Panel(str(exc), title="Error", border_style="red"))
        return

    if not corrected_steps:
        console.print(
            Panel("Could not generate a corrected command.", border_style="red")
        )
        return

    _process_step(
        step=corrected_steps[0],
        idx=idx,
        total=total,
        intent=intent,
        dry_run=dry_run,
        explain_flag=False,
        provider=provider,
        system_prompt=system_prompt,
        execution_mode=execution_mode,
    )


def _render_plan_summary(steps: list[Step], total: int) -> None:
    """Print a plan overview table showing which steps will auto-run vs need approval."""
    from rich.table import Table  # noqa: PLC0415

    table = Table(title=f"Plan — {total} steps", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Command", style="bold")
    table.add_column("Action", width=18)

    for i, step in enumerate(steps, start=1):
        level = classify_danger(step["command"], step["danger_level"])
        emoji = danger_emoji(level)
        if level == "safe":
            action = "[green]auto-run[/green]"
        else:
            action = f"[yellow]will ask ({level})[/yellow]"
        table.add_row(str(i), step["command"], f"{emoji} {action}")

    console.print(table)
    console.print()


def _show_explanation(provider: LLMProvider, command: str) -> None:
    """Fetch and display a per-token explanation of *command*."""
    try:
        raw = _call_llm(provider, "", _build_explain_prompt(command), label="Explaining")
        console.print(
            Panel(raw.strip(), title="Explanation", border_style="blue")
        )
    except Exception as exc:
        console.print(Panel(str(exc), title="Error", border_style="red"))


def _parse_with_retry(
    provider: LLMProvider, system: str, user: str, raw: str
) -> list[Step]:
    """Parse LLM output into steps; retry once if JSON is malformed."""
    try:
        return _parse_steps(raw)
    except (json.JSONDecodeError, KeyError, TypeError):
        console.print("[dim]Response was not valid JSON — retrying...[/dim]")
        retry_user = (
            user
            + "\n\nIMPORTANT: Your previous response was not valid JSON. "
            "Reply ONLY with the JSON object, no extra text."
        )
        try:
            raw2 = _call_llm(provider, system, retry_user, label="Retrying")
            return _parse_steps(raw2)
        except Exception as exc:
            console.print(Panel(str(exc), title="Parse Error", border_style="red"))
            return []
