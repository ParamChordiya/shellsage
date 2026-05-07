"""Tests for shellsage.history — JSON persistence, capping, and clearing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import shellsage.history as history


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_session_history():
    """Clear in-memory session state before and after every test."""
    history._session_history.clear()
    history._enabled = True
    yield
    history._session_history.clear()
    history._enabled = True


@pytest.fixture()
def history_file(tmp_path, monkeypatch):
    """Redirect all history I/O to a temp file and return its Path."""
    fake_file = tmp_path / "history.json"
    monkeypatch.setattr(history, "_HISTORY_FILE", fake_file)
    return fake_file


# ---------------------------------------------------------------------------
# Save and load round-trip
# ---------------------------------------------------------------------------

class TestSaveAndLoad:
    def test_record_persists_entry_to_file(self, history_file):
        history.record("list files", "ls -la", True)
        assert history_file.exists()
        data = json.loads(history_file.read_text())
        assert len(data) == 1
        assert data[0]["intent"] == "list files"
        assert data[0]["command"] == "ls -la"
        assert data[0]["success"] is True

    def test_loaded_entry_matches_saved_entry(self, history_file):
        history.record("show dir", "pwd", True)
        entries = history._load_all()
        assert len(entries) == 1
        assert entries[0]["intent"] == "show dir"
        assert entries[0]["command"] == "pwd"
        assert entries[0]["success"] is True

    def test_timestamp_is_recorded(self, history_file):
        history.record("check date", "date", True)
        data = json.loads(history_file.read_text())
        assert "timestamp" in data[0]
        assert len(data[0]["timestamp"]) > 0

    def test_failure_entry_saved_correctly(self, history_file):
        history.record("bad command", "notacommand", False)
        data = json.loads(history_file.read_text())
        assert data[0]["success"] is False


# ---------------------------------------------------------------------------
# Multiple entries
# ---------------------------------------------------------------------------

class TestMultipleEntries:
    def test_five_entries_all_persisted(self, history_file):
        for i in range(5):
            history.record(f"intent {i}", f"cmd{i}", True)
        data = json.loads(history_file.read_text())
        assert len(data) == 5

    def test_entries_preserved_in_order(self, history_file):
        commands = ["cmd0", "cmd1", "cmd2", "cmd3", "cmd4"]
        for i, cmd in enumerate(commands):
            history.record(f"intent {i}", cmd, True)
        data = json.loads(history_file.read_text())
        for i, cmd in enumerate(commands):
            assert data[i]["command"] == cmd

    def test_ten_entries_all_present(self, history_file):
        for i in range(10):
            history.record(f"intent {i}", f"cmd {i}", i % 2 == 0)
        entries = history._load_all()
        assert len(entries) == 10


# ---------------------------------------------------------------------------
# Cap at MAX_ENTRIES (200)
# ---------------------------------------------------------------------------

class TestCapAtMaxEntries:
    def test_adding_entry_beyond_cap_drops_oldest(self, history_file):
        # Pre-populate with MAX_ENTRIES entries via direct file write
        existing = [
            {"intent": f"i{n}", "command": f"c{n}", "success": True, "timestamp": "2024-01-01 00:00:00"}
            for n in range(history.MAX_ENTRIES)
        ]
        history_file.write_text(json.dumps(existing))

        # Now record one more — total would be 201, oldest must be dropped
        history.record("new intent", "new cmd", True)

        data = json.loads(history_file.read_text())
        assert len(data) == history.MAX_ENTRIES

    def test_oldest_entry_is_dropped(self, history_file):
        existing = [
            {"intent": "oldest", "command": "oldest_cmd", "success": True, "timestamp": "2024-01-01 00:00:00"}
        ] + [
            {"intent": f"i{n}", "command": f"c{n}", "success": True, "timestamp": "2024-01-01 00:00:00"}
            for n in range(history.MAX_ENTRIES - 1)
        ]
        history_file.write_text(json.dumps(existing))

        history.record("newest", "newest_cmd", True)

        data = json.loads(history_file.read_text())
        assert len(data) == history.MAX_ENTRIES
        # The very first entry ("oldest") should have been dropped
        commands = [e["command"] for e in data]
        assert "oldest_cmd" not in commands
        assert "newest_cmd" in commands

    def test_newest_entry_is_kept_after_cap(self, history_file):
        existing = [
            {"intent": f"i{n}", "command": f"c{n}", "success": True, "timestamp": "2024-01-01 00:00:00"}
            for n in range(history.MAX_ENTRIES)
        ]
        history_file.write_text(json.dumps(existing))

        history.record("keep this", "keep_cmd", True)

        data = json.loads(history_file.read_text())
        assert data[-1]["command"] == "keep_cmd"


# ---------------------------------------------------------------------------
# Clear history
# ---------------------------------------------------------------------------

class TestClearHistory:
    def test_clear_removes_history_file(self, history_file):
        history.record("some intent", "some cmd", True)
        assert history_file.exists()
        history.clear_history()
        assert not history_file.exists()

    def test_clear_empties_in_memory_history(self, history_file):
        history.record("intent", "cmd", True)
        assert len(history._session_history) == 1
        history.clear_history()
        assert len(history._session_history) == 0

    def test_clear_when_no_file_exists_does_not_crash(self, history_file):
        # File doesn't exist — clear_history should be a no-op
        assert not history_file.exists()
        history.clear_history()  # must not raise

    def test_get_history_returns_empty_after_clear(self, history_file):
        history.record("some", "cmd", True)
        history.clear_history()
        assert history.get_history() == []


# ---------------------------------------------------------------------------
# Corrupted file recovery
# ---------------------------------------------------------------------------

class TestCorruptedFileRecovery:
    def test_invalid_json_returns_empty_list(self, history_file):
        history_file.write_text("this is not valid json }{][")
        entries = history._load_all()
        assert entries == []

    def test_invalid_json_does_not_crash_record(self, history_file):
        history_file.write_text("CORRUPTED")
        # Should not raise — persistence is best-effort
        history.record("intent", "cmd", True)

    def test_invalid_json_is_overwritten_on_next_record(self, history_file):
        history_file.write_text("CORRUPTED")
        history.record("intent", "new_cmd", True)
        data = json.loads(history_file.read_text())
        assert len(data) == 1
        assert data[0]["command"] == "new_cmd"

    def test_array_of_non_dicts_returns_empty(self, history_file):
        history_file.write_text(json.dumps([1, 2, 3, "string", None]))
        entries = history._load_all()
        assert entries == []


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------

class TestMissingFile:
    def test_load_all_returns_empty_when_file_missing(self, history_file):
        assert not history_file.exists()
        entries = history._load_all()
        assert entries == []

    def test_get_history_returns_empty_when_no_session_entries(self):
        entries = history.get_history()
        assert entries == []


# ---------------------------------------------------------------------------
# Persistence across calls (simulating process restart)
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_data_survives_reload(self, history_file):
        """Simulate two separate 'processes': write in one call, read in another."""
        history.record("restart test", "echo restart", True)

        # Simulate a fresh load (as a new process would do)
        entries = history._load_all()
        assert len(entries) == 1
        assert entries[0]["intent"] == "restart test"
        assert entries[0]["command"] == "echo restart"

    def test_multiple_records_accumulate_on_disk(self, history_file):
        history.record("first", "cmd1", True)
        history.record("second", "cmd2", False)
        history.record("third", "cmd3", True)

        entries = history._load_all()
        assert len(entries) == 3
        assert entries[0]["command"] == "cmd1"
        assert entries[1]["command"] == "cmd2"
        assert entries[2]["command"] == "cmd3"


# ---------------------------------------------------------------------------
# configure() (enable/disable)
# ---------------------------------------------------------------------------

class TestConfigure:
    def test_disabled_history_does_not_persist(self, history_file):
        history.configure(enabled=False)
        history.record("ignored intent", "ignored_cmd", True)
        assert not history_file.exists()

    def test_disabled_history_does_not_add_to_session(self):
        history.configure(enabled=False)
        history.record("ignored intent", "ignored_cmd", True)
        assert history._session_history == []

    def test_re_enabled_history_records_again(self, history_file):
        history.configure(enabled=False)
        history.record("skipped", "skip_cmd", True)
        history.configure(enabled=True)
        history.record("recorded", "rec_cmd", True)
        data = json.loads(history_file.read_text())
        assert len(data) == 1
        assert data[0]["command"] == "rec_cmd"


# ---------------------------------------------------------------------------
# get_history returns copy of in-memory session entries
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_returns_copy_not_reference(self, history_file):
        history.record("intent", "cmd", True)
        copy1 = history.get_history()
        copy1.clear()
        # Original should still have 1 entry
        assert len(history._session_history) == 1

    def test_session_history_matches_records(self, history_file):
        history.record("a", "cmd_a", True)
        history.record("b", "cmd_b", False)
        entries = history.get_history()
        assert len(entries) == 2
        assert entries[0]["command"] == "cmd_a"
        assert entries[1]["command"] == "cmd_b"
