import json
import os
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fluid_voice.config import (
    ConfigManager,
    ConfigData,
    Top8PromptRanker,
    get_app_data_dir,
    KEYRING_SERVICE,
    KEYRING_USER_GROQ,
)


def test_get_app_data_dir_default_and_custom_env(tmp_path):
    """Tier 1: Verifies get_app_data_dir returns valid Path and supports LOCALAPPDATA override."""
    # Default app data dir
    app_dir = get_app_data_dir()
    assert isinstance(app_dir, Path)
    assert app_dir.exists()

    # Custom LOCALAPPDATA override
    custom_appdata = tmp_path / "CustomAppData"
    old_env = os.environ.get("LOCALAPPDATA")
    try:
        os.environ["LOCALAPPDATA"] = str(custom_appdata)
        override_dir = get_app_data_dir()
        assert override_dir == custom_appdata / "FluidVoice"
        assert override_dir.exists()
    finally:
        if old_env is not None:
            os.environ["LOCALAPPDATA"] = old_env
        else:
            os.environ.pop("LOCALAPPDATA", None)


def test_config_manager_default_values(tmp_path):
    """Tier 1: Verifies ConfigManager initializes with default values when config file does not exist."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    data = config_mgr.data

    assert isinstance(data, ConfigData)
    assert data.hotkey == "Ctrl+Shift"
    assert data.vad_silence_duration_s == 1.5
    assert data.max_recording_duration_s == 30
    assert data.auto_paste is True
    assert data.start_with_windows is False
    assert data.theme == "dark"
    assert data.groq_api_key_fallback == ""

    # Verify config.json file was created automatically
    config_file = tmp_path / "config.json"
    assert config_file.exists()


def test_config_manager_saving_and_loading(tmp_path):
    """Tier 1: Verifies updating configuration fields persists correctly to disk."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.update(hotkey="Alt+S", max_recording_duration_s=45, theme="light")

    assert config_mgr.data.hotkey == "Alt+S"
    assert config_mgr.data.max_recording_duration_s == 45
    assert config_mgr.data.theme == "light"

    # Reload in a fresh instance
    new_config_mgr = ConfigManager(config_dir=tmp_path)
    assert new_config_mgr.data.hotkey == "Alt+S"
    assert new_config_mgr.data.max_recording_duration_s == 45
    assert new_config_mgr.data.theme == "light"


def test_config_manager_atomic_save_no_leftover_tmp(tmp_path):
    """Tier 2: Verifies atomic write uses temporary file and leaves no residual tmp files."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.update(auto_paste=False)

    config_file = tmp_path / "config.json"
    assert config_file.exists()

    with open(config_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    assert json_data["auto_paste"] is False

    temp_file = tmp_path / "config.json.tmp"
    assert not temp_file.exists()


def test_config_manager_update_ignores_invalid_keys(tmp_path):
    """Tier 2: Verifies update ignores unknown/invalid config attributes."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.update(hotkey="Alt+S", invalid_key_name="should_be_ignored")

    assert config_mgr.data.hotkey == "Alt+S"
    assert not hasattr(config_mgr.data, "invalid_key_name")


def test_config_manager_corrupted_json_recovery(tmp_path):
    """Tier 2: Verifies corrupted/invalid JSON content recovers gracefully to defaults."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{corrupted: json data...", encoding="utf-8")

    config_mgr = ConfigManager(config_dir=tmp_path)
    assert config_mgr.data.hotkey == "Ctrl+Shift"
    assert config_mgr.data.max_recording_duration_s == 30

    # Verify config.json was overwritten with valid default JSON
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["hotkey"] == "Ctrl+Shift"


def test_api_key_keyring_success_storage(tmp_path):
    """Tier 1: Verifies Groq API key storage in OS credential keyring."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = "gsk_keyring_api_key_123"

    with patch("fluid_voice.config.HAS_KEYRING", True), \
         patch("fluid_voice.config.keyring", mock_keyring):

        success = config_mgr.set_api_key("gsk_keyring_api_key_123")

        assert success is True
        mock_keyring.set_password.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USER_GROQ, "gsk_keyring_api_key_123"
        )
        assert config_mgr.get_api_key() == "gsk_keyring_api_key_123"
        assert config_mgr.data.groq_api_key_fallback == ""


def test_api_key_keyring_failure_fallback_to_json(tmp_path):
    """Tier 2: Verifies Groq API key fallback to JSON storage when keyring write fails."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    mock_keyring = MagicMock()
    mock_keyring.set_password.side_effect = RuntimeError("Keyring access denied")
    mock_keyring.get_password.side_effect = RuntimeError("Keyring unavailable")

    with patch("fluid_voice.config.HAS_KEYRING", True), \
         patch("fluid_voice.config.keyring", mock_keyring):

        success = config_mgr.set_api_key("gsk_fallback_key_456")

        assert success is False
        assert config_mgr.get_api_key() == "gsk_fallback_key_456"
        assert config_mgr.data.groq_api_key_fallback == "gsk_fallback_key_456"

        # Verify fallback key was saved in config.json
        config_file = tmp_path / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            saved_json = json.load(f)
        assert saved_json["groq_api_key_fallback"] == "gsk_fallback_key_456"


def test_api_key_no_keyring_module_fallback(tmp_path):
    """Tier 2: Verifies fallback to JSON storage when keyring module is not available."""
    config_mgr = ConfigManager(config_dir=tmp_path)

    with patch("fluid_voice.config.HAS_KEYRING", False), \
         patch("fluid_voice.config.keyring", None):

        success = config_mgr.set_api_key("gsk_no_keyring_789")

        assert success is False
        assert config_mgr.get_api_key() == "gsk_no_keyring_789"
        assert config_mgr.data.groq_api_key_fallback == "gsk_no_keyring_789"


def test_api_key_empty_key_clears_storage(tmp_path):
    """Tier 2: Verifies setting empty API key clears keyring password and JSON fallback."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    mock_keyring = MagicMock()

    with patch("fluid_voice.config.HAS_KEYRING", True), \
         patch("fluid_voice.config.keyring", mock_keyring):

        config_mgr.set_api_key("gsk_initial_key")
        mock_keyring.reset_mock()

        success = config_mgr.set_api_key("")
        assert success is True
        mock_keyring.delete_password.assert_called_once_with(KEYRING_SERVICE, KEYRING_USER_GROQ)
        assert config_mgr.data.groq_api_key_fallback == ""


def test_environment_variable_override_groq_api_key(tmp_path):
    """Tier 2: Verifies GROQ_API_KEY environment variable takes highest priority."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.data.groq_api_key_fallback = "gsk_json_fallback_key"

    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_env_override_key_999"}):
        assert config_mgr.get_api_key() == "gsk_env_override_key_999"


def test_environment_variable_override_hotkey(tmp_path):
    """Tier 2: Verifies FLUID_VOICE_HOTKEY environment variable overrides config on load."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"hotkey": "Ctrl+Shift+V"}), encoding="utf-8")

    with patch.dict(os.environ, {"FLUID_VOICE_HOTKEY": "Alt+P"}):
        config_mgr = ConfigManager(config_dir=tmp_path)
        assert config_mgr.data.hotkey == "Alt+P"


def test_config_manager_thread_safety(tmp_path):
    """Tier 2: Verifies thread-safe concurrent modifications to ConfigManager."""
    config_mgr = ConfigManager(config_dir=tmp_path)

    def worker(val: int):
        for _ in range(15):
            config_mgr.update(max_recording_duration_s=val)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert config_mgr.data.max_recording_duration_s in range(5)


def test_top8_prompt_ranker_token_capping():
    """R1: Verifies Context-Aware Top-8 Prompt Ranker selects up to 8 terms and enforces strictly <150 token cap."""
    # 1. Test top-8 selection
    many_terms = [f"Term{i}" for i in range(15)]
    prompt_top8 = Top8PromptRanker.rank_and_build_prompt(terms=many_terms)
    assert "Term0" in prompt_top8
    assert "Term7" in prompt_top8
    assert "Term8" not in prompt_top8  # Only top 8 included

    # 2. Test strict token capping under 150 tokens
    long_terms = ["VeryLongDomainSpecificJargonTermForTestingCapping" * 5 for _ in range(10)]
    capped_prompt = Top8PromptRanker.rank_and_build_prompt(terms=long_terms)
    tokens = Top8PromptRanker.estimate_tokens(capped_prompt)
    assert tokens < 150
