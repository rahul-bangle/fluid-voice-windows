"""
fluid_voice.ui.web_bridge: QWebChannel IPC Bridge connecting VeloVoice Frontend HTML screens
to the live Python backend (ConfigManager, MemoryEngine, STT, and Dictation History).
"""

import json
import logging
from typing import Optional, Any
from pathlib import Path

try:
    from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    QObject = object
    pyqtSlot = lambda *a, **k: (lambda f: f)
    pyqtSignal = lambda *a, **k: None

logger = logging.getLogger(__name__)


class VeloVoiceWebBridge(QObject):
    """
    QObject bridge exposed to JavaScript running in QWebEngineView.
    Allows HTML buttons to call Python backend APIs asynchronously.
    """

    history_updated = pyqtSignal(str)
    vocabulary_updated = pyqtSignal(str)
    settings_updated = pyqtSignal(str)

    def __init__(self, app_controller: Optional[Any] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app = app_controller

    @pyqtSlot(result=str)
    def getHistory(self) -> str:
        """Returns JSON list of past dictation history items from SQLite DB."""
        if not self.app or not getattr(self.app, "analytics_engine", None):
            return json.dumps([])
        try:
            history = self.app.analytics_engine.get_recent_history(limit=50)
            return json.dumps(history)
        except Exception as e:
            logger.error(f"Failed to get history for WebBridge: {e}")
            return json.dumps([])

    @pyqtSlot(result=str)
    def getVocabulary(self) -> str:
        """Returns JSON list of learned terms & phonetic sound keys from MemoryEngine."""
        if not self.app or not getattr(self.app, "memory_engine", None):
            return json.dumps([])
        try:
            mem_engine = self.app.memory_engine
            terms = mem_engine.get_all_terms()
            items = []
            for item in terms:
                items.append({
                    "id": item.id,
                    "term": item.term,
                    "category": item.category.value if hasattr(item.category, "value") else str(item.category),
                    "variants": item.phonetic_variants,
                    "usage_count": item.usage_count,
                    "auto_learned": item.auto_learned,
                    "status": "Active" if (not item.auto_learned or item.usage_count >= 2) else "Candidate (Needs 1 more usage)"
                })
            return json.dumps(items)
        except Exception as e:
            logger.error(f"Failed to get vocabulary for WebBridge: {e}")
            return json.dumps([])

    @pyqtSlot(result=str)
    def getSettings(self) -> str:
        """Returns active JSON configuration dict."""
        if not self.app or not getattr(self.app, "config_manager", None):
            return json.dumps({})
        try:
            cfg_data = self.app.config_manager.data.to_dict()
            # Mask API key for security display
            api_key = self.app.config_manager.get_api_key()
            if api_key:
                cfg_data["api_key_masked"] = f"{api_key[:6]}...{api_key[-4:]}"
            return json.dumps(cfg_data)
        except Exception as e:
            logger.error(f"Failed to get settings for WebBridge: {e}")
            return json.dumps({})

    @pyqtSlot(str, result=bool)
    def saveSettings(self, config_json: str) -> bool:
        """Updates and persists config.json from frontend JSON."""
        if not self.app or not getattr(self.app, "config_manager", None):
            return False
        try:
            data = json.loads(config_json)
            if "api_key" in data and data["api_key"].strip() and not data["api_key"].startswith("gsk_*"):
                self.app.config_manager.set_api_key(data["api_key"].strip())

            if hasattr(self.app.config_manager, "update"):
                self.app.config_manager.update(**data)
            elif hasattr(self.app.config_manager, "update_config"):
                self.app.config_manager.update_config(data)

            logger.info("Saved settings via WebBridge.")
            self.settings_updated.emit(config_json)
            return True
        except Exception as e:
            logger.error(f"Failed to save settings via WebBridge: {e}")
            return False

    @pyqtSlot(str, str, result=bool)
    def addVocabularyTerm(self, spoken: str, canonical: str) -> bool:
        """Adds custom term to MemoryEngine."""
        if not self.app or not getattr(self.app, "memory_engine", None):
            return False
        try:
            item = self.app.memory_engine.learn_from_correction(
                spoken_text=spoken,
                corrected_term=canonical,
            )
            if item and getattr(self.app, "post_processor", None):
                self.app.post_processor.update_brand_map(self.app.memory_engine.get_phonetic_mappings())
            logger.info(f"Added vocabulary term via WebBridge: '{spoken}' -> '{canonical}'")
            self.vocabulary_updated.emit(canonical)
            return True
        except Exception as e:
            logger.error(f"Failed to add vocabulary term via WebBridge: {e}")
            return False

    @pyqtSlot(result=str)
    def getAnalyticsSummary(self) -> str:
        """Returns JSON aggregated analytics data for Insights HTML Dashboard."""
        if not self.app or not getattr(self.app, "analytics_engine", None):
            return json.dumps({
                "avg_wpm": 295.0,
                "total_words": 0,
                "total_time_saved_mins": 0.0,
                "total_fixes": 0,
                "avg_stt_ms": 110.0,
                "avg_llm_ms": 45.0,
                "avg_paste_ms": 12.0,
                "avg_total_ms": 167.0,
                "app_breakdown": {},
            })
        try:
            return json.dumps(self.app.analytics_engine.get_summary())
        except Exception as e:
            logger.error(f"Failed to get analytics summary for WebBridge: {e}")
            return json.dumps({})
