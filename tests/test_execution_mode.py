"""Tests for the execution-mode feature (ask_all vs auto_safe)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

import shellsage.config as config
from shellsage.agent import _process_step, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(command: str = "ls -la", danger_level: str = "safe") -> Step:
    return Step(command=command, explanation="test step", danger_level=danger_level)


def _make_provider() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# Config: get_execution_mode
# ---------------------------------------------------------------------------

class TestGetExecutionMode:
    def test_returns_ask_all_by_default(self):
        with patch.object(config, "load", return_value={"preferences": {}}):
            assert config.get_execution_mode() == "ask_all"

    def test_returns_auto_safe_when_set(self):
        with patch.object(config, "load", return_value={
            "preferences": {"execution_mode": "auto_safe"}
        }):
            assert config.get_execution_mode() == "auto_safe"

    def test_falls_back_for_invalid_value(self):
        with patch.object(config, "load", return_value={
            "preferences": {"execution_mode": "unknown_value"}
        }):
            assert config.get_execution_mode() == "ask_all"

    def test_returns_ask_all_when_explicitly_set(self):
        with patch.object(config, "load", return_value={
            "preferences": {"execution_mode": "ask_all"}
        }):
            assert config.get_execution_mode() == "ask_all"


# ---------------------------------------------------------------------------
# ask_all mode: always prompts
# ---------------------------------------------------------------------------

class TestAskAllMode:
    def test_prompts_for_safe_command(self):
        step = _make_step("ls -la", "safe")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask", return_value="y"):
            mock_exec.return_value = MagicMock(success=True, stdout="", stderr="")
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="ask_all",
            )
            mock_exec.assert_called_once()

    def test_prompts_for_caution_command(self):
        step = _make_step("sudo apt update", "caution")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask", return_value="n"):
            mock_exec.return_value = MagicMock(success=True, stdout="", stderr="")
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="ask_all",
            )
            # User said n — should NOT execute
            mock_exec.assert_not_called()

    def test_skips_on_n_answer(self):
        step = _make_step("ls", "safe")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.Prompt.ask", return_value="n"):
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="ask_all",
            )
            mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# auto_safe mode: runs safe automatically, prompts for others
# ---------------------------------------------------------------------------

class TestAutoSafeMode:
    def test_auto_runs_safe_command_without_prompt(self):
        step = _make_step("ls -la", "safe")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask") as mock_prompt:
            mock_exec.return_value = MagicMock(success=True, stdout="", stderr="")
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="auto_safe",
            )
            # Command ran automatically
            mock_exec.assert_called_once_with("ls -la", dry_run=False)
            # No prompt was shown
            mock_prompt.assert_not_called()

    def test_prompts_for_caution_command_in_auto_safe_mode(self):
        step = _make_step("sudo apt update", "caution")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask", return_value="y"):
            mock_exec.return_value = MagicMock(success=True, stdout="", stderr="")
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="auto_safe",
            )
            # Prompted because level is caution
            mock_exec.assert_called_once()

    def test_prompts_for_destructive_command_in_auto_safe_mode(self):
        step = _make_step("rm -rf ./old", "destructive")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask", return_value="n"):
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="auto_safe",
            )
            # User declined — should not run
            mock_exec.assert_not_called()

    def test_auto_safe_respects_local_danger_escalation(self):
        """A command the LLM labels 'safe' but our patterns escalate to 'caution'
        must NOT be auto-run — the effective level determines the behaviour."""
        # 'sudo' triggers caution escalation regardless of llm_level
        step = _make_step("sudo ls", "safe")
        with patch("shellsage.agent.is_blocked", return_value=False), \
             patch("shellsage.agent._render_step"), \
             patch("shellsage.agent.execute") as mock_exec, \
             patch("shellsage.agent.history.record"), \
             patch("shellsage.agent.Prompt.ask", return_value="y"):
            mock_exec.return_value = MagicMock(success=True, stdout="", stderr="")
            _process_step(
                step=step, idx=1, total=1, intent="test",
                dry_run=False, explain_flag=False,
                provider=_make_provider(), system_prompt="",
                execution_mode="auto_safe",
            )
            # Prompt was shown (not auto-run) because effective level is caution
            mock_exec.assert_called_once()

    def test_blocklist_always_blocks_regardless_of_mode(self):
        step = _make_step("rm -rf /", "safe")
        with patch("shellsage.agent.is_blocked", return_value=True), \
             patch("shellsage.agent.execute") as mock_exec:
            with pytest.raises(SystemExit):
                _process_step(
                    step=step, idx=1, total=1, intent="test",
                    dry_run=False, explain_flag=False,
                    provider=_make_provider(), system_prompt="",
                    execution_mode="auto_safe",
                )
            mock_exec.assert_not_called()
