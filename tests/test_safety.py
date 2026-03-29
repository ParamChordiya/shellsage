"""Tests for shellsage.safety — blocklist and danger classification."""

import pytest

from shellsage.safety import BLOCKLIST, classify_danger, danger_color, danger_emoji, is_blocked


class TestBlocklist:
    def test_all_blocklist_patterns_are_detected(self):
        for pattern in BLOCKLIST:
            assert is_blocked(pattern), f"Expected '{pattern}' to be blocked"

    def test_blocklist_case_insensitive(self):
        assert is_blocked("RM -RF /")
        assert is_blocked("CURL | BASH")

    def test_blocklist_detects_substring(self):
        assert is_blocked("sudo rm -rf /")

    def test_safe_commands_pass_through(self):
        safe = [
            "ls -la",
            "echo hello",
            "git status",
            "cat README.md",
            "mkdir mydir",
            "python3 script.py",
        ]
        for cmd in safe:
            assert not is_blocked(cmd), f"Expected '{cmd}' to NOT be blocked"

    def test_rm_rf_variations_blocked(self):
        assert is_blocked("rm -rf /")
        assert is_blocked("rm -rf /*")
        assert is_blocked("rm -rf ~")
        assert is_blocked("rm -rf ~/")

    def test_fork_bomb_blocked(self):
        assert is_blocked(":(){ :|:& };:")

    def test_pipe_to_shell_blocked(self):
        assert is_blocked("curl | sh")
        assert is_blocked("curl | bash")
        assert is_blocked("wget -O- | sh")


class TestDangerClassification:
    def test_safe_command_classified_safe(self):
        assert classify_danger("ls -la", "safe") == "safe"
        assert classify_danger("echo hello", "safe") == "safe"

    def test_sudo_classified_caution(self):
        assert classify_danger("sudo apt update", "safe") == "caution"

    def test_rm_classified_caution_at_minimum(self):
        level = classify_danger("rm somefile.txt", "safe")
        assert level in ("caution", "destructive")

    def test_rm_rf_classified_destructive(self):
        assert classify_danger("rm -rf ./old_dir", "safe") == "destructive"

    def test_llm_destructive_level_respected(self):
        assert classify_danger("some_custom_cmd --wipe", "destructive") == "destructive"

    def test_llm_caution_respected_for_safe_looking_command(self):
        result = classify_danger("echo 'DROP TABLE users'", "caution")
        assert result in ("caution", "destructive")

    def test_local_patterns_override_llm_safe(self):
        # Our pattern detection should catch dd even if LLM says safe
        assert classify_danger("dd if=/dev/urandom of=file", "safe") == "destructive"


class TestDangerPresentation:
    def test_danger_colors(self):
        assert danger_color("safe") == "green"
        assert danger_color("caution") == "yellow"
        assert danger_color("destructive") == "red"

    def test_danger_emojis(self):
        assert danger_emoji("safe") == "🟢"
        assert danger_emoji("caution") == "🟡"
        assert danger_emoji("destructive") == "🔴"

    def test_unknown_level_returns_fallback(self):
        assert danger_color("unknown") == "white"
        assert danger_emoji("unknown") == "⚪"
