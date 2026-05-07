"""Tests for shellsage.executor — subprocess runner with timeout and dry-run."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from shellsage.executor import ExecutionResult, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

class TestBasicExecution:
    def test_echo_hello_returns_stdout(self):
        result = run("echo hello", timeout=5)
        assert result.success is True
        assert "hello" in result.stdout

    def test_returns_execution_result_named_tuple(self):
        result = run("echo test", timeout=5)
        assert isinstance(result, ExecutionResult)
        assert hasattr(result, "success")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")

    def test_multi_word_command_with_arguments(self):
        result = run("echo one two three", timeout=5)
        assert result.success is True
        assert "one" in result.stdout
        assert "two" in result.stdout
        assert "three" in result.stdout


# ---------------------------------------------------------------------------
# Exit code capture
# ---------------------------------------------------------------------------

class TestExitCodeCapture:
    def test_failing_command_returns_non_zero_exit(self):
        result = run("false", timeout=5)
        assert result.success is False

    def test_success_flag_is_true_for_zero_exit(self):
        mock_proc = _make_completed_process(returncode=0, stdout="ok\n")
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.success is True

    def test_success_flag_is_false_for_nonzero_exit(self):
        mock_proc = _make_completed_process(returncode=1, stderr="error")
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.success is False

    def test_exit_code_2_returns_failure(self):
        mock_proc = _make_completed_process(returncode=2, stderr="bad usage")
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.success is False


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

class TestDryRunMode:
    def test_dry_run_does_not_call_subprocess(self):
        with patch("subprocess.run") as mock_run:
            result = run("echo hello", dry_run=True, timeout=5)
        mock_run.assert_not_called()

    def test_dry_run_returns_success(self):
        result = run("echo hello", dry_run=True, timeout=5)
        assert result.success is True

    def test_dry_run_returns_empty_stdout_stderr(self):
        result = run("echo hello", dry_run=True, timeout=5)
        assert result.stdout == ""
        assert result.stderr == ""

    def test_dry_run_true_skips_dangerous_command(self):
        """Even a destructive-looking command should not be executed in dry-run."""
        with patch("subprocess.run") as mock_run:
            result = run("rm -rf /tmp/nonexistent", dry_run=True, timeout=5)
        mock_run.assert_not_called()
        assert result.success is True


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

class TestTimeoutHandling:
    def test_timeout_expired_returns_failure(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 100", timeout=1)):
            result = run("sleep 100", timeout=1)
        assert result.success is False

    def test_timeout_expired_stderr_contains_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 100", timeout=1)):
            result = run("sleep 100", timeout=1)
        assert "timeout" in result.stderr.lower()

    def test_timeout_expired_stdout_is_empty(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 100", timeout=1)):
            result = run("sleep 100", timeout=1)
        assert result.stdout == ""

    def test_zero_timeout_means_no_timeout(self):
        """timeout=0 should translate to no timeout (None passed to subprocess)."""
        mock_proc = _make_completed_process(returncode=0, stdout="done\n")
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = run("echo done", timeout=0)
        assert result.success is True
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] is None


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------

class TestOutputCapture:
    def test_stdout_is_captured_and_returned(self):
        mock_proc = _make_completed_process(returncode=0, stdout="captured output\n")
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.stdout == "captured output\n"

    def test_stderr_is_captured_and_returned(self):
        mock_proc = _make_completed_process(returncode=1, stderr="error message\n")
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.stderr == "error message\n"

    def test_both_stdout_and_stderr_captured(self):
        mock_proc = _make_completed_process(
            returncode=0, stdout="out\n", stderr="err\n"
        )
        with patch("subprocess.run", return_value=mock_proc):
            result = run("somecommand", timeout=5)
        assert result.stdout == "out\n"
        assert result.stderr == "err\n"

    def test_subprocess_called_with_shell_true(self):
        mock_proc = _make_completed_process(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            run("echo hello", timeout=5)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is True

    def test_subprocess_called_with_capture_output(self):
        mock_proc = _make_completed_process(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            run("echo hello", timeout=5)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True

    def test_subprocess_called_with_text_mode(self):
        mock_proc = _make_completed_process(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            run("echo hello", timeout=5)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["text"] is True


# ---------------------------------------------------------------------------
# Generic exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    def test_generic_exception_returns_failure(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = run("bogus_command", timeout=5)
        assert result.success is False

    def test_generic_exception_propagates_message_to_stderr(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = run("bogus_command", timeout=5)
        assert "no such file" in result.stderr

    def test_generic_exception_stdout_is_empty(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = run("bogus_command", timeout=5)
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# Timeout defaults from config
# ---------------------------------------------------------------------------

class TestTimeoutDefault:
    def test_timeout_none_reads_from_config(self):
        """When timeout is not provided, it should be read from config."""
        mock_proc = _make_completed_process(returncode=0, stdout="hi\n")
        with patch("shellsage.config.get_timeout", return_value=30) as mock_cfg, \
             patch("subprocess.run", return_value=mock_proc):
            result = run("echo hi")
        mock_cfg.assert_called_once()
        assert result.success is True

    def test_explicit_timeout_overrides_config(self):
        """Explicit timeout=5 should not call config.get_timeout."""
        mock_proc = _make_completed_process(returncode=0)
        with patch("shellsage.config.get_timeout") as mock_cfg, \
             patch("subprocess.run", return_value=mock_proc):
            run("echo hi", timeout=5)
        mock_cfg.assert_not_called()
