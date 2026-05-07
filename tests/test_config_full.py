"""Tests for shellsage.config — load/save, deep-merge, defaults, and path handling."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import tomli_w

import shellsage.config as config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cfg_paths(tmp_path, monkeypatch):
    """Redirect all config I/O to a temp directory."""
    cfg_dir = tmp_path / ".shellsage"
    cfg_file = cfg_dir / "config.toml"
    env_file = cfg_dir / ".env"

    monkeypatch.setattr(config, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "_CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config, "_ENV_FILE", env_file)

    return {"dir": cfg_dir, "file": cfg_file, "env": env_file}


# ---------------------------------------------------------------------------
# Load defaults
# ---------------------------------------------------------------------------

class TestLoadDefaults:
    def test_returns_defaults_when_no_config_file(self, cfg_paths):
        assert not cfg_paths["file"].exists()
        cfg = config.load()
        assert cfg["provider"]["type"] == "ollama"
        assert cfg["provider"]["model"] == "llama3.2"
        assert cfg["preferences"]["execution_mode"] == "ask_all"
        assert cfg["preferences"]["timeout"] == 30
        assert cfg["preferences"]["save_history"] is True

    def test_all_top_level_default_keys_present(self, cfg_paths):
        cfg = config.load()
        assert "provider" in cfg
        assert "preferences" in cfg

    def test_default_ollama_url_present(self, cfg_paths):
        cfg = config.load()
        assert cfg["provider"]["ollama_url"] == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Save and reload
# ---------------------------------------------------------------------------

class TestSaveAndReload:
    def test_saved_config_can_be_reloaded(self, cfg_paths):
        cfg = config.load()
        cfg["provider"]["type"] = "claude"
        config.save(cfg)
        reloaded = config.load()
        assert reloaded["provider"]["type"] == "claude"

    def test_save_creates_config_file(self, cfg_paths):
        assert not cfg_paths["file"].exists()
        config.save(config.load())
        assert cfg_paths["file"].exists()

    def test_all_values_survive_round_trip(self, cfg_paths):
        original = config.load()
        original["provider"]["type"] = "claude"
        original["provider"]["model"] = "claude-opus-4"
        original["preferences"]["execution_mode"] = "auto_safe"
        original["preferences"]["timeout"] = 60
        original["preferences"]["save_history"] = False

        config.save(original)
        reloaded = config.load()

        assert reloaded["provider"]["type"] == "claude"
        assert reloaded["provider"]["model"] == "claude-opus-4"
        assert reloaded["preferences"]["execution_mode"] == "auto_safe"
        assert reloaded["preferences"]["timeout"] == 60
        assert reloaded["preferences"]["save_history"] is False

    def test_save_writes_toml_format(self, cfg_paths):
        config.save(config.load())
        raw = cfg_paths["file"].read_text()
        # TOML files have key = value lines
        assert "=" in raw


# ---------------------------------------------------------------------------
# Deep merge with partial config
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_partial_config_missing_keys_get_defaults(self, cfg_paths):
        # Write a partial TOML with only provider.type set
        partial = {"provider": {"type": "claude"}}
        cfg_paths["file"].parent.mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_bytes(tomli_w.dumps(partial).encode())

        cfg = config.load()
        # Explicitly set key is retained
        assert cfg["provider"]["type"] == "claude"
        # Missing keys in provider section get defaults
        assert cfg["provider"]["model"] == "llama3.2"
        assert cfg["provider"]["ollama_url"] == "http://localhost:11434"
        # Entire preferences section gets defaults
        assert cfg["preferences"]["execution_mode"] == "ask_all"
        assert cfg["preferences"]["timeout"] == 30

    def test_partial_preferences_keeps_unset_as_default(self, cfg_paths):
        partial = {"preferences": {"timeout": 120}}
        cfg_paths["file"].parent.mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_bytes(tomli_w.dumps(partial).encode())

        cfg = config.load()
        assert cfg["preferences"]["timeout"] == 120
        # Other preferences fall back to defaults
        assert cfg["preferences"]["execution_mode"] == "ask_all"
        assert cfg["preferences"]["save_history"] is True

    def test_deep_merge_does_not_mutate_defaults(self, cfg_paths):
        """Loading config must not alter the module-level _DEFAULTS dict."""
        defaults_before = copy.deepcopy(config._DEFAULTS)
        partial = {"provider": {"type": "claude"}}
        cfg_paths["file"].parent.mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_bytes(tomli_w.dumps(partial).encode())

        config.load()
        assert config._DEFAULTS == defaults_before

    def test_extra_keys_in_file_are_preserved(self, cfg_paths):
        """Unknown keys from the file should survive into the merged result."""
        partial = {"provider": {"type": "ollama", "custom_key": "custom_value"}}
        cfg_paths["file"].parent.mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_bytes(tomli_w.dumps(partial).encode())

        cfg = config.load()
        assert cfg["provider"].get("custom_key") == "custom_value"


# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

class TestConfigPath:
    def test_config_dir_creates_directory(self, cfg_paths):
        assert not cfg_paths["dir"].exists()
        returned = config.config_dir()
        assert cfg_paths["dir"].exists()
        assert returned == cfg_paths["dir"]

    def test_config_exists_returns_false_when_missing(self, cfg_paths):
        assert config.config_exists() is False

    def test_config_exists_returns_true_after_save(self, cfg_paths):
        config.save(config.load())
        assert config.config_exists() is True

    def test_save_writes_to_correct_path(self, cfg_paths):
        config.save(config.load())
        assert cfg_paths["file"].exists()
        # No file was written anywhere else
        other_files = list(cfg_paths["dir"].iterdir())
        assert cfg_paths["file"] in other_files


# ---------------------------------------------------------------------------
# Invalid TOML falls back to defaults
# ---------------------------------------------------------------------------

class TestInvalidTomlFallback:
    def test_corrupted_toml_returns_defaults(self, cfg_paths):
        cfg_paths["dir"].mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_text("this is not valid toml = = =")
        cfg = config.load()
        # Must return defaults without raising
        assert cfg["provider"]["type"] == "ollama"
        assert cfg["preferences"]["execution_mode"] == "ask_all"

    def test_corrupted_toml_does_not_raise(self, cfg_paths):
        cfg_paths["dir"].mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_text("}{][invalid")
        # Should not raise
        cfg = config.load()
        assert isinstance(cfg, dict)

    def test_empty_file_treated_as_defaults(self, cfg_paths):
        cfg_paths["dir"].mkdir(parents=True, exist_ok=True)
        cfg_paths["file"].write_text("")
        cfg = config.load()
        # Empty TOML is valid and results in empty dict → all defaults
        assert cfg["provider"]["type"] == "ollama"


# ---------------------------------------------------------------------------
# Provider type round-trip
# ---------------------------------------------------------------------------

class TestProviderTypeRoundTrip:
    def test_ollama_provider_round_trip(self, cfg_paths):
        cfg = config.load()
        cfg["provider"]["type"] = "ollama"
        config.save(cfg)
        reloaded = config.load()
        assert config.get_provider_type(reloaded) == "ollama"

    def test_claude_provider_round_trip(self, cfg_paths):
        cfg = config.load()
        cfg["provider"]["type"] = "claude"
        config.save(cfg)
        reloaded = config.load()
        assert config.get_provider_type(reloaded) == "claude"

    def test_get_provider_type_defaults_to_ollama(self, cfg_paths):
        assert config.get_provider_type({}) == "ollama"

    def test_get_provider_model_defaults_to_llama(self, cfg_paths):
        assert config.get_provider_model({}) == "llama3.2"

    def test_get_ollama_url_default(self, cfg_paths):
        assert "11434" in config.get_ollama_url({})


# ---------------------------------------------------------------------------
# get_timeout
# ---------------------------------------------------------------------------

class TestGetTimeout:
    def test_default_timeout_is_30(self, cfg_paths):
        assert config.get_timeout({}) == 30

    def test_timeout_zero_returns_zero(self, cfg_paths):
        cfg = {"preferences": {"timeout": 0}}
        assert config.get_timeout(cfg) == 0

    def test_timeout_negative_clamped_to_zero(self, cfg_paths):
        cfg = {"preferences": {"timeout": -10}}
        assert config.get_timeout(cfg) == 0

    def test_invalid_timeout_type_returns_default(self, cfg_paths):
        cfg = {"preferences": {"timeout": "not_a_number"}}
        assert config.get_timeout(cfg) == 30

    def test_custom_timeout_round_trip(self, cfg_paths):
        cfg = config.load()
        cfg["preferences"]["timeout"] = 120
        config.save(cfg)
        reloaded = config.load()
        assert config.get_timeout(reloaded) == 120


# ---------------------------------------------------------------------------
# save_api_key
# ---------------------------------------------------------------------------

class TestSaveApiKey:
    def test_api_key_written_to_env_file(self, cfg_paths):
        config.save_api_key("sk-test-key-abc123")
        content = cfg_paths["env"].read_text()
        assert "sk-test-key-abc123" in content

    def test_env_file_has_restricted_permissions(self, cfg_paths):
        config.save_api_key("sk-test-key")
        mode = cfg_paths["env"].stat().st_mode & 0o777
        assert mode == 0o600

    def test_api_key_format_is_correct(self, cfg_paths):
        config.save_api_key("my-api-key")
        content = cfg_paths["env"].read_text()
        assert 'ANTHROPIC_API_KEY="my-api-key"' in content


# ---------------------------------------------------------------------------
# get_save_history and get_execution_mode (via config dict, no file I/O)
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_get_save_history_defaults_true(self):
        assert config.get_save_history({}) is True

    def test_get_save_history_false_when_set(self):
        cfg = {"preferences": {"save_history": False}}
        assert config.get_save_history(cfg) is False

    def test_get_execution_mode_defaults_ask_all(self):
        assert config.get_execution_mode({}) == "ask_all"

    def test_get_execution_mode_auto_safe(self):
        cfg = {"preferences": {"execution_mode": "auto_safe"}}
        assert config.get_execution_mode(cfg) == "auto_safe"

    def test_get_execution_mode_invalid_falls_back(self):
        cfg = {"preferences": {"execution_mode": "bad_value"}}
        assert config.get_execution_mode(cfg) == "ask_all"
