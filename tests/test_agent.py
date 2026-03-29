"""Tests for shellsage.agent — JSON parsing, retry logic, multi-step plans."""

import json
from unittest.mock import MagicMock, patch

import pytest

from shellsage.agent import _parse_steps, _parse_with_retry, Step


class TestParseSteps:
    def test_parses_single_step(self):
        raw = json.dumps({
            "steps": [
                {
                    "command": "ls -la",
                    "explanation": "List all files",
                    "danger_level": "safe",
                }
            ]
        })
        steps = _parse_steps(raw)
        assert len(steps) == 1
        assert steps[0]["command"] == "ls -la"
        assert steps[0]["explanation"] == "List all files"
        assert steps[0]["danger_level"] == "safe"

    def test_parses_multiple_steps(self):
        raw = json.dumps({
            "steps": [
                {"command": "mkdir newdir", "explanation": "Create directory", "danger_level": "safe"},
                {"command": "cd newdir", "explanation": "Enter directory", "danger_level": "safe"},
                {"command": "touch file.txt", "explanation": "Create file", "danger_level": "safe"},
            ]
        })
        steps = _parse_steps(raw)
        assert len(steps) == 3
        assert steps[0]["command"] == "mkdir newdir"
        assert steps[2]["command"] == "touch file.txt"

    def test_parses_all_danger_levels(self):
        for level in ("safe", "caution", "destructive"):
            raw = json.dumps({
                "steps": [{"command": "cmd", "explanation": "x", "danger_level": level}]
            })
            steps = _parse_steps(raw)
            assert steps[0]["danger_level"] == level

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({
            "steps": [{"command": "echo hi", "explanation": "greet", "danger_level": "safe"}]
        }) + "\n```"
        steps = _parse_steps(raw)
        assert len(steps) == 1
        assert steps[0]["command"] == "echo hi"

    def test_raises_on_invalid_json(self):
        with pytest.raises((json.JSONDecodeError, KeyError, TypeError, ValueError)):
            _parse_steps("not json at all")

    def test_returns_empty_on_wrong_structure(self):
        # Missing "steps" key → treated as empty plan, not an error
        steps = _parse_steps(json.dumps({"result": "something else"}))
        assert steps == []

    def test_empty_steps_list(self):
        raw = json.dumps({"steps": []})
        steps = _parse_steps(raw)
        assert steps == []


class TestParseWithRetry:
    def test_returns_steps_on_valid_json(self):
        provider = MagicMock()
        raw = json.dumps({
            "steps": [{"command": "ls", "explanation": "list", "danger_level": "safe"}]
        })
        steps = _parse_with_retry(provider, "sys", "usr", raw)
        assert len(steps) == 1
        provider.complete.assert_not_called()

    def test_retries_on_malformed_json(self):
        provider = MagicMock()
        valid_response = json.dumps({
            "steps": [{"command": "pwd", "explanation": "print dir", "danger_level": "safe"}]
        })
        # Mock the LLM live spinner call
        with patch("shellsage.agent._call_llm", return_value=valid_response):
            steps = _parse_with_retry(provider, "sys", "usr", "INVALID JSON !!!!")
        assert len(steps) == 1
        assert steps[0]["command"] == "pwd"

    def test_returns_empty_list_when_retry_also_fails(self):
        provider = MagicMock()
        with patch("shellsage.agent._call_llm", side_effect=RuntimeError("API error")):
            steps = _parse_with_retry(provider, "sys", "usr", "INVALID")
        assert steps == []

    def test_no_retry_needed_for_valid_response(self):
        provider = MagicMock()
        raw = json.dumps({
            "steps": [{"command": "git status", "explanation": "check git", "danger_level": "safe"}]
        })
        with patch("shellsage.agent._call_llm") as mock_call:
            steps = _parse_with_retry(provider, "sys", "usr", raw)
        mock_call.assert_not_called()
        assert steps[0]["command"] == "git status"


class TestMultiStepPlans:
    def test_multi_step_count_matches(self):
        n_steps = 5
        raw = json.dumps({
            "steps": [
                {"command": f"cmd{i}", "explanation": f"step {i}", "danger_level": "safe"}
                for i in range(n_steps)
            ]
        })
        steps = _parse_steps(raw)
        assert len(steps) == n_steps

    def test_step_order_preserved(self):
        commands = ["step_a", "step_b", "step_c"]
        raw = json.dumps({
            "steps": [
                {"command": cmd, "explanation": "x", "danger_level": "safe"}
                for cmd in commands
            ]
        })
        steps = _parse_steps(raw)
        for i, cmd in enumerate(commands):
            assert steps[i]["command"] == cmd

    def test_step_has_required_keys(self):
        raw = json.dumps({
            "steps": [{"command": "ls", "explanation": "list files", "danger_level": "safe"}]
        })
        steps = _parse_steps(raw)
        for step in steps:
            assert "command" in step
            assert "explanation" in step
            assert "danger_level" in step
