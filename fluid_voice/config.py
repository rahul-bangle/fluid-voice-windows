import os
import json
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, asdict, fields

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "FluidVoice"
KEYRING_USER_GROQ = "groq_api_key"

try:
    import keyring
    HAS_KEYRING = True
except Exception as err:
    keyring = None
    HAS_KEYRING = False
    logger.warning(f"Keyring module import failed: {err}. Using JSON storage fallback.")


def get_app_data_dir() -> Path:
    """Returns the platform-specific AppData path for FluidVoice settings."""
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "FluidVoice"
    else:
        path = Path.home() / ".config" / "FluidVoice"
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULT_ENGLISH_PROMPT = (
    "Hi Rahul, how may I help you today? Please deploy the latest Docker container to Kubernetes "
    "and review the pull request. Everything is working smoothly. Thanks!"
)
DEFAULT_HINGLISH_PROMPT = DEFAULT_ENGLISH_PROMPT


@dataclass
class ConfigData:
    """Application configuration schema with defaults."""
    hotkey: str = "Alt+S"
    vad_silence_threshold_db: float = -40.0
    vad_silence_duration_s: float = 1.5
    max_recording_duration_s: int = 30
    auto_paste: bool = True
    start_with_windows: bool = False
    theme: str = "dark"
    hinglish_prompt: str = DEFAULT_ENGLISH_PROMPT
    language: str = "en"
    groq_api_key_fallback: str = ""


class ConfigManager:
    """
    Thread-safe configuration manager for FluidVoice.
    Handles AppData storage (%LOCALAPPDATA%\\FluidVoice\\config.json), keyring storage
    for API keys with JSON fallback, and atomic file saving.
    """

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or get_app_data_dir()
        self.config_file = self.config_dir / "config.json"
        self._lock = threading.RLock()
        self._data = ConfigData()
        self.load()

    @property
    def data(self) -> ConfigData:
        with self._lock:
            return self._data

    def load(self) -> ConfigData:
        """Loads configuration from JSON file. Saves default if missing."""
        with self._lock:
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    valid_keys = {f.name for f in fields(ConfigData)}
                    for k, v in content.items():
                        if k in valid_keys:
                            setattr(self._data, k, v)
                except Exception as e:
                    logger.error(f"Failed to load config from {self.config_file}: {e}. Resetting to defaults.")
                    self.save()
            else:
                self.save()

            env_hotkey = os.getenv("FLUID_VOICE_HOTKEY")
            if env_hotkey:
                self._data.hotkey = env_hotkey

            return self._data

    def save(self) -> None:
        """Atomically saves configuration to JSON file using a temp file."""
        with self._lock:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            temp_file = self.config_file.with_suffix(".json.tmp")
            try:
                data_dict = asdict(self._data)
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data_dict, f, indent=2)
                temp_file.replace(self.config_file)
            except Exception as e:
                logger.error(f"Failed to save config to {self.config_file}: {e}")
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass

    def update(self, **kwargs) -> None:
        """Updates config fields and persists changes atomically."""
        with self._lock:
            valid_keys = {f.name for f in fields(ConfigData)}
            updated = False
            for k, v in kwargs.items():
                if k in valid_keys:
                    setattr(self._data, k, v)
                    updated = True
            if updated:
                self.save()

    def get_api_key(self) -> str:
        """
        Retrieves the Groq API key.
        Checks GROQ_API_KEY environment variable first, then OS credential keyring,
        falling back to JSON storage if keyring fails or is empty.
        """
        with self._lock:
            env_key = os.getenv("GROQ_API_KEY")
            if env_key:
                return env_key
            if HAS_KEYRING and keyring is not None:
                try:
                    key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_GROQ)
                    if key:
                        return key
                except Exception as e:
                    logger.warning(f"Keyring read failed: {e}. Falling back to config.json.")
            return self._data.groq_api_key_fallback

    def set_api_key(self, api_key: str) -> bool:
        """
        Saves the Groq API key to OS credential keyring.
        If keyring fails or is unavailable, falls back to storing in config.json.
        Returns True if keyring storage succeeded, False if fallback was used.
        """
        with self._lock:
            keyring_success = False
            if HAS_KEYRING and keyring is not None:
                try:
                    if api_key:
                        keyring.set_password(KEYRING_SERVICE, KEYRING_USER_GROQ, api_key)
                    else:
                        try:
                            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER_GROQ)
                        except Exception:
                            pass
                    keyring_success = True
                except Exception as e:
                    logger.warning(f"Keyring write failed: {e}. Using JSON fallback.")

            if keyring_success:
                self._data.groq_api_key_fallback = ""
            else:
                self._data.groq_api_key_fallback = api_key
            
            self.save()
            return keyring_success
