"""Tests for shellsage.chat — ChatSession, REPL loop, multi-turn accumulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, call, patch

import pytest

from shellsage.chat import (
    ChatSession,
    _call_llm_chat,
    _parse_with_retry_chat,
    _process_step_chat,
)
from shellsage.executor import ExecutionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> ChatSession:
    defaults = dict(
        provider=MagicMock(),
        system_prompt="you are shellsage",
        dry_run=False,
        explain_flag=False,
        execution_mode="ask_all",
    )
    defaults.update(kwargs)
    return ChatSession(**defaults)


def _valid_json(command: str = "ls -la", danger: str = "safe") -> str:
    return json.dumps({
        "steps": [{"command": command, "explanation": "test", "danger_level": danger}]
    })


# ---------------------------------------------------------------------------
# ChatSession unit tests
# ---------------------------------------------------------------------------

class TestChatSession:
    def test_add_user_message(self):
        s = _make_session()
        s.add_user_message("hello")
        assert s.messages == [{"role": "user", "content": "hello"}]

    def test_add_assistant_message(self):
        s = _make_session()
        s.add_assistant_message("here is a command")
        assert s.messages == [{"role": "assistant", "content": "here is a command"}]

    def test_add_execution_result_success(self):
        s = _make_session()
        result = ExecutionResult(success=True, stdout="file.txt\n", stderr="")
        s.add_execution_result("ls", result)
        msg = s.messages[-1]
        assert msg["role"] == "user"
        assert "success" in msg["content"]
        assert "file.txt" in msg["content"]
        assert "ls" in msg["content"]

    def test_add_execution_result_failure(self):
        s = _make_session()
        result = ExecutionResult(success=False, stdout="", stderr="command not found")
        s.add_execution_result("badcmd", result)
        msg = s.messages[-1]
        assert "failure" in msg["content"]
        assert "command not found" in msg["content"]

    def test_add_execution_result_empty_output(self):
        s = _make_session()
        result = ExecutionResult(success=True, stdout="", stderr="")
        s.add_execution_result("touch file", result)
        msg = s.messages[-1]
        assert "(empty)" in msg["content"]

    def test_add_skipped_command(self):
        s = _make_session()
        s.add_skipped_command("rm -rf ./old")
        msg = s.messages[-1]
        assert msg["role"] == "user"
        assert "not to run" in msg["content"]
        assert "rm -rf ./old" in msg["content"]

    def test_add_dry_run_command(self):
        s = _make_session()
        s.add_dry_run_command("echo hello")
        msg = s.messages[-1]
        assert "dry-run" in msg["content"]
        assert "echo hello" in msg["content"]

    def test_messages_order_preserved(self):
        s = _make_session()
        s.add_user_message("turn 1")
        s.add_assistant_message("reply 1")
        s.add_user_message("turn 2")
        s.add_assistant_message("reply 2")
        roles = [m["role"] for m in s.messages]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_messages_starts_empty(self):
        s = _make_session()
        assert s.messages == []


# ---------------------------------------------------------------------------
# _call_llm_chat
# ---------------------------------------------------------------------------

class TestCallLlmChat:
    def test_passes_full_messages_to_provider(self):
        provider = MagicMock()
        provider.complete.return_value = "response"
        s = _make_session(provider=provider)
        s.add_user_message("what should I do?")

        result = _call_llm_chat(s)

        assert result == "response"
        provider.complete.assert_called_once_with(
            system=s.system_prompt,
            user="",
            messages=s.messages,
        )

    def test_raises_on_provider_error(self):
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("connection refused")
        s = _make_session(provider=provider)
        s.add_user_message("hello")

        with pytest.raises(RuntimeError, match="connection refused"):
            _call_llm_chat(s)


# ---------------------------------------------------------------------------
# _parse_with_retry_chat
# ---------------------------------------------------------------------------

class TestParseWithRetryChat:
    def test_returns_steps_on_valid_json(self):
        s = _make_session()
        raw = _valid_json("echo hi")
        steps = _parse_with_retry_chat(s, raw)
        assert len(steps) == 1
        assert steps[0]["command"] == "echo hi"
        # No retry message added
        assert len(s.messages) == 0

    def test_retries_on_bad_json_and_appends_to_conversation(self):
        provider = MagicMock()
        provider.complete.return_value = _valid_json("pwd")
        s = _make_session(provider=provider)

        steps = _parse_with_retry_chat(s, "NOT JSON")

        # A retry user message was appended
        assert any("not valid JSON" in m["content"].upper() or
                   "not valid json" in m["content"].lower()
                   for m in s.messages if m["role"] == "user")
        assert len(steps) == 1
        assert steps[0]["command"] == "pwd"

    def test_returns_empty_list_when_retry_also_fails(self):
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("API down")
        s = _make_session(provider=provider)

        steps = _parse_with_retry_chat(s, "NOT JSON")
        assert steps == []


# ---------------------------------------------------------------------------
# _process_step_chat
# ---------------------------------------------------------------------------

class TestProcessStepChat:
    def _make_step(self, cmd="ls -la", danger="safe"):
        return {"command": cmd, "explanation": "test", "danger_level": danger}

    def test_executes_on_y_and_records_history(self):
        s = _make_session()
        step = self._make_step()
        with patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.history.record") as mock_hist, \
             patch("shellsage.chat.Prompt.ask", return_value="y"):
            mock_exec.return_value = ExecutionResult(True, "output", "")
            _process_step_chat(s, step, 1, 1, "list files")
            mock_exec.assert_called_once()
            mock_hist.assert_called_once()

    def test_execution_result_added_to_session(self):
        s = _make_session()
        step = self._make_step()
        with patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.history.record"), \
             patch("shellsage.chat.Prompt.ask", return_value="y"):
            mock_exec.return_value = ExecutionResult(True, "hello", "")
            _process_step_chat(s, step, 1, 1, "intent")
        # Execution result should be in the session messages
        assert any("Command executed" in m["content"] for m in s.messages)

    def test_skip_adds_skipped_message(self):
        s = _make_session()
        step = self._make_step()
        with patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.Prompt.ask", return_value="n"):
            _process_step_chat(s, step, 1, 1, "intent")
            mock_exec.assert_not_called()
        assert any("not to run" in m["content"] for m in s.messages)

    def test_blocked_command_does_not_exit_repl(self):
        """Blocked commands in chat should not call sys.exit — just return."""
        s = _make_session()
        step = self._make_step("rm -rf /")
        with patch("shellsage.chat.is_blocked", return_value=True), \
             patch("shellsage.chat.execute") as mock_exec:
            # Should NOT raise SystemExit inside chat mode
            _process_step_chat(s, step, 1, 1, "intent")
            mock_exec.assert_not_called()
        assert any("blocked" in m["content"].lower() for m in s.messages)

    def test_auto_safe_runs_without_prompt(self):
        s = _make_session(execution_mode="auto_safe")
        step = self._make_step("ls", "safe")
        with patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.history.record"), \
             patch("shellsage.chat.Prompt.ask") as mock_prompt:
            mock_exec.return_value = ExecutionResult(True, "", "")
            _process_step_chat(s, step, 1, 1, "intent")
            mock_exec.assert_called_once()
            mock_prompt.assert_not_called()

    def test_dry_run_adds_dry_run_message(self):
        s = _make_session(dry_run=True)
        step = self._make_step()
        with patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.history.record"), \
             patch("shellsage.chat.Prompt.ask", return_value="y"):
            mock_exec.return_value = ExecutionResult(True, "", "")
            _process_step_chat(s, step, 1, 1, "intent")
        assert any("dry-run" in m["content"] for m in s.messages)


# ---------------------------------------------------------------------------
# REPL loop (run_chat)
# ---------------------------------------------------------------------------

class TestRunChat:
    def _mock_provider_complete(self, command="echo hi"):
        return _valid_json(command)

    def test_exit_terminates_loop(self):
        from shellsage.chat import run_chat
        provider = MagicMock()
        with patch("shellsage.chat._make_provider", return_value=provider), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", return_value="exit"):
            run_chat()
        provider.complete.assert_not_called()

    def test_quit_terminates_loop(self):
        from shellsage.chat import run_chat
        with patch("shellsage.chat._make_provider", return_value=MagicMock()), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", return_value="quit"):
            run_chat()  # should not hang

    def test_empty_input_does_not_call_llm(self):
        from shellsage.chat import run_chat
        provider = MagicMock()
        inputs = iter(["", "  ", "q"])
        with patch("shellsage.chat._make_provider", return_value=provider), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", side_effect=inputs):
            run_chat()
        provider.complete.assert_not_called()

    def test_single_turn_executes_and_records(self):
        from shellsage.chat import run_chat
        provider = MagicMock()
        provider.complete.return_value = _valid_json("ls -la")
        inputs = iter(["list files", "q"])
        with patch("shellsage.chat._make_provider", return_value=provider), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", side_effect=inputs), \
             patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute") as mock_exec, \
             patch("shellsage.chat.history.record") as mock_hist, \
             patch("shellsage.chat.Prompt.ask", return_value="y"):
            mock_exec.return_value = ExecutionResult(True, "output", "")
            run_chat()
        mock_exec.assert_called_once()
        mock_hist.assert_called_once()

    def test_multi_turn_accumulates_messages(self):
        from shellsage.chat import run_chat
        provider = MagicMock()
        provider.complete.return_value = _valid_json("ls")
        inputs = iter(["turn 1", "turn 2", "turn 3", "q"])

        captured_sessions = []
        original_call = None

        def capture_complete(system, user, messages=None):
            if messages is not None:
                captured_sessions.append(list(messages))
            return _valid_json("ls")

        provider.complete.side_effect = capture_complete

        with patch("shellsage.chat._make_provider", return_value=provider), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", side_effect=inputs), \
             patch("shellsage.chat.is_blocked", return_value=False), \
             patch("shellsage.chat._render_step"), \
             patch("shellsage.chat.execute", return_value=ExecutionResult(True, "", "")), \
             patch("shellsage.chat.history.record"), \
             patch("shellsage.chat.Prompt.ask", return_value="y"):
            run_chat()

        # By the 3rd LLM call, messages must include all prior turns
        assert len(captured_sessions) == 3
        # Each successive call should have more messages
        assert len(captured_sessions[1]) > len(captured_sessions[0])
        assert len(captured_sessions[2]) > len(captured_sessions[1])

    def test_keyboard_interrupt_is_handled(self):
        from shellsage.chat import run_chat
        with patch("shellsage.chat._make_provider", return_value=MagicMock()), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", side_effect=[KeyboardInterrupt, "q"]):
            run_chat()  # should not propagate the KeyboardInterrupt

    def test_llm_error_continues_loop(self):
        """If the LLM call fails, the REPL should show an error and continue."""
        from shellsage.chat import run_chat
        provider = MagicMock()
        provider.complete.side_effect = [RuntimeError("API down"), None]
        inputs = iter(["do something", "q"])
        with patch("shellsage.chat._make_provider", return_value=provider), \
             patch("shellsage.chat.get_context"), \
             patch("shellsage.chat._build_system_prompt", return_value="sys"), \
             patch("shellsage.chat.config.load", return_value={}), \
             patch("shellsage.chat.config.get_execution_mode", return_value="ask_all"), \
             patch("shellsage.chat.console.input", side_effect=inputs):
            run_chat()  # should not crash despite the first call failing
