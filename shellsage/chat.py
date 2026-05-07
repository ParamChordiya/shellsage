"""Multi-turn interactive chat mode for ShellSage.

`run_chat()` enters a Rich-styled REPL where the full conversation history
(user requests, LLM responses, and command output) is accumulated and sent
to the LLM on every turn.  The single-shot agent flow in agent.py is
completely untouched — this module is an independent code path.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner

import shellsage.config as config
import shellsage.history as history
from shellsage.agent import (
    _build_correction_prompt,
    _build_multi_correction_prompt,
    _build_system_prompt,
    _make_provider,
    _parse_steps,
    _render_step,
    _show_explanation,
)
from shellsage.config import get_max_retries
from shellsage.context import get_context
from shellsage.executor import ExecutionResult, run as execute
from shellsage.providers.base import LLMProvider
from shellsage.safety import classify_danger, is_blocked

console = Console()


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

@dataclass
class ChatSession:
    """Holds all state for one interactive chat session."""

    provider: LLMProvider
    system_prompt: str
    dry_run: bool
    explain_flag: bool
    execution_mode: str
    max_retries: int = 3
    messages: list[dict[str, str]] = field(default_factory=list)

    # ---- message helpers -------------------------------------------------

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_execution_result(self, command: str, result: ExecutionResult) -> None:
        """Inject command output back into the conversation."""
        status = "success" if result.success else "failure"
        stdout = result.stdout.strip() or "(empty)"
        stderr = result.stderr.strip() or "(empty)"
        content = (
            f"Command executed: `{command}`\n"
            f"Exit status: {status}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
        self.add_user_message(content)

    def add_skipped_command(self, command: str) -> None:
        self.add_user_message(f"The user chose not to run: `{command}`")

    def add_dry_run_command(self, command: str) -> None:
        self.add_user_message(f"(dry-run) Command shown but not executed: `{command}`")


# ---------------------------------------------------------------------------
# LLM wrapper
# ---------------------------------------------------------------------------

def _call_llm_chat(session: ChatSession, label: str = "Thinking") -> str:
    """Call the provider with the full conversation history, inside a spinner."""
    result_holder: list[str] = []
    error_holder: list[Exception] = []

    spinner = Spinner("dots", text=f"[dim]{label}...[/dim]")
    with Live(spinner, console=console, refresh_per_second=10):
        try:
            result_holder.append(
                session.provider.complete(
                    system=session.system_prompt,
                    user="",  # ignored when messages is provided
                    messages=session.messages,
                )
            )
        except Exception as exc:
            error_holder.append(exc)

    if error_holder:
        raise error_holder[0]
    return result_holder[0]


# ---------------------------------------------------------------------------
# JSON parsing with conversation-aware retry
# ---------------------------------------------------------------------------

def _parse_with_retry_chat(session: ChatSession, raw: str) -> list:
    """Parse LLM output; on failure append a correction message and retry once."""
    try:
        return _parse_steps(raw)
    except (json.JSONDecodeError, KeyError, TypeError):
        console.print("[dim]Response was not valid JSON — retrying...[/dim]")
        retry_msg = (
            "IMPORTANT: Your previous response was not valid JSON. "
            "Reply ONLY with the JSON object, no extra text or markdown."
        )
        session.add_user_message(retry_msg)
        try:
            raw2 = _call_llm_chat(session, label="Retrying")
            session.add_assistant_message(raw2)
            return _parse_steps(raw2)
        except Exception as exc:
            console.print(Panel(str(exc), title="Parse Error", border_style="red"))
            return []


# ---------------------------------------------------------------------------
# Step processing (chat-aware)
# ---------------------------------------------------------------------------

def _process_step_chat(
    session: ChatSession,
    step: dict,
    idx: int,
    total: int,
    intent: str,
) -> None:
    """Handle one step inside a chat session: render, confirm, execute, self-correct."""
    if is_blocked(step["command"]):
        console.print(
            Panel(
                f"[bold red]{step['command']}[/bold red]\n\n"
                "This command matches the hard blocklist and cannot be run.",
                title="Blocked",
                border_style="red",
            )
        )
        # Don't exit the whole REPL — just skip this step
        session.add_user_message(
            f"The command `{step['command']}` was blocked by the safety system."
        )
        return

    effective_level = classify_danger(step["command"], step["danger_level"])
    auto_run = session.execution_mode == "auto_safe" and effective_level == "safe"

    _render_step(step, idx, total)

    if auto_run:
        console.print("[dim]Auto-running (safe command)...[/dim]")
        result = execute(step["command"], dry_run=session.dry_run)
        history.record(intent=intent, command=step["command"], success=result.success)
        if session.dry_run:
            session.add_dry_run_command(step["command"])
        else:
            session.add_execution_result(step["command"], result)
        if not result.success and not session.dry_run:
            _self_correct_chat(session, step, idx, total, intent, result.stderr)
        return

    if session.explain_flag:
        _show_explanation(session.provider, step["command"])

    while True:
        answer = Prompt.ask(
            "[bold]Run this?[/bold] [dim](y / n / e to explain)[/dim]",
            choices=["y", "n", "e"],
            default="y",
        ).lower()

        if answer == "n":
            console.print("[dim]Skipped.[/dim]")
            session.add_skipped_command(step["command"])
            return

        if answer == "e":
            _show_explanation(session.provider, step["command"])
            continue

        # answer == "y"
        result = execute(step["command"], dry_run=session.dry_run)
        history.record(intent=intent, command=step["command"], success=result.success)

        if session.dry_run:
            session.add_dry_run_command(step["command"])
            return

        session.add_execution_result(step["command"], result)

        if result.success:
            return

        _self_correct_chat(session, step, idx, total, intent, result.stderr)
        return


def _self_correct_chat(
    session: ChatSession,
    step: dict,
    idx: int,
    total: int,
    intent: str,
    stderr: str,
) -> None:
    """Ask the LLM to fix a failed command, retrying up to session.max_retries times.

    Uses the full conversation history for context. Each subsequent attempt
    receives a richer prompt with all prior failed corrections.
    """
    original_command = step["command"]
    failed_attempts: list[tuple[str, str]] = []
    current_step = step
    current_stderr = stderr
    max_retries = session.max_retries

    for attempt in range(1, max_retries + 1):
        console.print(
            Panel(
                current_stderr or "(no stderr output)",
                title=f"Command failed — self-correction attempt {attempt}/{max_retries}",
                border_style="yellow",
            )
        )

        if attempt == 1:
            correction_msg = _build_correction_prompt(
                current_step["command"], current_stderr
            )
        else:
            correction_msg = _build_multi_correction_prompt(
                original_command, failed_attempts
            )

        session.add_user_message(correction_msg)

        try:
            raw = _call_llm_chat(
                session,
                label=f"Correcting (attempt {attempt}/{max_retries})",
            )
            session.add_assistant_message(raw)
            corrected_steps = _parse_with_retry_chat(session, raw)
        except Exception as exc:
            console.print(Panel(str(exc), title="Error", border_style="red"))
            return

        if not corrected_steps:
            console.print(
                Panel("Could not generate a corrected command.", border_style="red")
            )
            return

        corrected_step = corrected_steps[0]

        if is_blocked(corrected_step["command"]):
            console.print(
                Panel(
                    f"[bold red]{corrected_step['command']}[/bold red]\n\n"
                    "Corrected command matches the hard blocklist and cannot be run.",
                    title="Blocked",
                    border_style="red",
                )
            )
            session.add_user_message(
                f"The corrected command `{corrected_step['command']}` was blocked."
            )
            return

        _render_step(corrected_step, idx, total)

        # Prompt user before running corrected command (unless auto_safe + safe)
        corrected_level = classify_danger(
            corrected_step["command"], corrected_step["danger_level"]
        )
        needs_prompt = session.execution_mode != "auto_safe" or corrected_level != "safe"
        if needs_prompt:
            answer = Prompt.ask(
                "[bold]Run corrected command?[/bold] [dim](y / n)[/dim]",
                choices=["y", "n"],
                default="y",
            ).lower()
            if answer == "n":
                console.print("[dim]Skipped.[/dim]")
                session.add_skipped_command(corrected_step["command"])
                return

        correction_result = execute(
            corrected_step["command"], dry_run=session.dry_run
        )
        history.record(
            intent=intent,
            command=corrected_step["command"],
            success=correction_result.success,
        )

        if session.dry_run:
            session.add_dry_run_command(corrected_step["command"])
            return

        session.add_execution_result(corrected_step["command"], correction_result)

        if correction_result.success:
            return

        # Record this failed attempt and loop again
        failed_attempts.append((corrected_step["command"], correction_result.stderr))
        current_step = corrected_step
        current_stderr = correction_result.stderr

    # All retries exhausted
    console.print(
        Panel(
            f"Self-correction failed after {max_retries} attempt(s). "
            "The command could not be fixed automatically.",
            title="Self-Correction Exhausted",
            border_style="red",
        )
    )
    session.add_user_message(
        f"Self-correction exhausted after {max_retries} attempt(s). "
        "Please try a different approach."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_chat(
    dry_run: bool = False,
    explain_flag: bool = False,
    provider_override: Optional[str] = None,
) -> None:
    """Enter the interactive multi-turn chat REPL."""
    cfg = config.load()
    execution_mode = config.get_execution_mode(cfg)
    max_retries = get_max_retries(cfg)

    try:
        provider = _make_provider(provider_override)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Error", border_style="red"))
        sys.exit(1)

    ctx = get_context()
    system_prompt = _build_system_prompt(ctx)

    session = ChatSession(
        provider=provider,
        system_prompt=system_prompt,
        dry_run=dry_run,
        explain_flag=explain_flag,
        execution_mode=execution_mode,
        max_retries=max_retries,
    )

    console.print(
        Panel(
            "[bold cyan]ShellSage Chat[/bold cyan]\n\n"
            "Describe what you want to do in plain English.\n"
            "Your full conversation is remembered across turns.\n\n"
            "[dim]Commands:[/dim]  [bold]exit[/bold] / [bold]quit[/bold] / [bold]q[/bold]  to leave   "
            "[bold]Ctrl+C[/bold]  to interrupt",
            title="Interactive Mode",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = console.input("\n[bold cyan]shellsage>[/bold cyan] ").strip()
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type exit to quit.[/dim]")
            continue
        except EOFError:
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            break

        session.add_user_message(user_input)

        try:
            raw = _call_llm_chat(session)
        except RuntimeError as exc:
            console.print(Panel(str(exc), title="Error", border_style="red"))
            # Remove the user message we just added so the history stays clean
            session.messages.pop()
            continue

        session.add_assistant_message(raw)

        steps = _parse_with_retry_chat(session, raw)
        if not steps:
            console.print(
                Panel(
                    "Could not parse a command from that response. Try rephrasing.",
                    border_style="yellow",
                )
            )
            continue

        total = len(steps)
        for idx, step in enumerate(steps, start=1):
            _process_step_chat(session, step, idx, total, intent=user_input)

    console.print("[dim]Goodbye.[/dim]")
