import os
import sys
import ctypes
import signal
import logging
from enum import Enum, auto
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, QMetaObject, Qt, pyqtSlot

from fluid_voice.config import ConfigManager, get_app_data_dir
from fluid_voice.tray import FluidVoiceTrayIcon, TrayState
from fluid_voice.hotkey import HotkeyListener
from fluid_voice.audio import AudioRecorder
from fluid_voice.stt_groq import GroqSTTClient, InvalidAPIKeyError
from fluid_voice.post_processor import HinglishPostProcessor
from fluid_voice.ui.overlay import OverlayWidget
from fluid_voice.ui.settings import SettingsDialog
from fluid_voice.paster import AutoPaster

logger = logging.getLogger(__name__)

SINGLE_INSTANCE_MUTEX_NAME = "Global\\FluidVoice_SingleInstance_Mutex"


class AppState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    PASTING = auto()
    ERROR = auto()


class FluidVoiceApp(QObject):
    """
    Core Application Controller for FluidVoice.
    Glues together HotkeyListener, AudioRecorder, GroqSTTClient, HinglishPostProcessor,
    OverlayWidget, AutoPaster, SystemTrayIcon, and SettingsDialog.
    """
    state_changed = pyqtSignal(object, str)  # (AppState, message)

    def __init__(self, sys_argv=None, config_dir: Path | None = None, mutex_name: str | None = None):
        super().__init__()
        self.sys_argv = sys_argv or sys.argv
        self.qt_app = QApplication.instance() or QApplication(self.sys_argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setApplicationName("FluidVoice")

        self.mutex_name = mutex_name or SINGLE_INSTANCE_MUTEX_NAME
        self._mutex_handle = None
        self._lock_file_path = (config_dir or get_app_data_dir()) / "app.lock"
        self._state = AppState.IDLE
        self._target_hwnd = 0

        # Core Subsystems
        self.config_manager = ConfigManager(config_dir=config_dir)
        self.tray_icon: FluidVoiceTrayIcon | None = None
        self.hotkey_engine: HotkeyListener | None = None
        self.audio_recorder: AudioRecorder | None = None
        self.stt_client: GroqSTTClient | None = None
        self.post_processor: HinglishPostProcessor | None = None
        self.overlay_widget: OverlayWidget | None = None
        self.paster_engine: AutoPaster | None = None

    @property
    def current_state(self) -> AppState:
        return self._state

    def _check_single_instance(self) -> bool:
        """
        Enforces a single running instance of FluidVoice.
        Uses Win32 named mutex on Windows, with a lockfile fallback.
        """
        if sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                mutex = kernel32.CreateMutexW(None, False, self.mutex_name)
                last_error = kernel32.GetLastError()
                ERROR_ALREADY_EXISTS = 183
                if last_error == ERROR_ALREADY_EXISTS:
                    logger.error(f"Another instance of FluidVoice is already running (Mutex: {self.mutex_name}).")
                    if mutex:
                        kernel32.CloseHandle(mutex)
                    return False
                self._mutex_handle = mutex
                return True
            except Exception as e:
                logger.warning(f"Win32 mutex check failed: {e}. Falling back to lockfile.")

        # Non-Windows or fallback lockfile check
        try:
            if self._lock_file_path.exists():
                logger.error(f"Lockfile exists at {self._lock_file_path}. Instance already running.")
                return False
            self._lock_file_path.write_text("locked", encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Lockfile creation failed: {e}")
            return True

    def initialize(self) -> bool:
        """Initializes system tray icon, subsystems, signal handlers, and sets initial app state."""
        if not self._check_single_instance():
            return False

        # Initialize System Tray Icon
        if self.tray_icon is None:
            self.tray_icon = FluidVoiceTrayIcon()
        self.tray_icon.recording_toggled.connect(self.toggle_recording)
        self.tray_icon.settings_requested.connect(self.open_settings)
        self.tray_icon.exit_requested.connect(self.quit)
        self.tray_icon.show()

        # Initialize AutoPaster Engine
        if self.paster_engine is None:
            self.paster_engine = AutoPaster()

        # Initialize Post Processor
        if self.post_processor is None:
            self.post_processor = HinglishPostProcessor()

        # Initialize Overlay Widget
        if self.overlay_widget is None:
            self.overlay_widget = OverlayWidget()

        # Initialize Audio Recorder
        if self.audio_recorder is None:
            self.audio_recorder = AudioRecorder(
                silence_duration_sec=self.config_manager.data.vad_silence_duration_s,
                max_duration_sec=float(self.config_manager.data.max_recording_duration_s),
            )
        self.audio_recorder.audio_level_changed.connect(self._on_audio_level_changed)
        self.audio_recorder.error_occurred.connect(self._on_audio_error)

        # Initialize STT Client if API key is present
        api_key = self.config_manager.get_api_key() or os.getenv("GROQ_API_KEY", "").strip()
        if api_key and self.stt_client is None:
            # Also save to config_manager so key persists
            self.config_manager.set_api_key(api_key)
            try:
                self.stt_client = GroqSTTClient(
                    api_key=api_key,
                    prompt=self.config_manager.data.hinglish_prompt,
                    language=None,
                )
            except Exception as e:
                logger.warning(f"Could not initialize GroqSTTClient on startup: {e}")

        # Initialize Hotkey Listener Engine
        if self.hotkey_engine is None:
            self.hotkey_engine = HotkeyListener(
                hotkey_str=self.config_manager.data.hotkey,
                on_keydown=self.start_recording,
                on_keyup=self.stop_recording,
            )
        if not self.hotkey_engine.is_running:
            self.hotkey_engine.start()

        # Wire Python signal handler for clean CLI termination (Ctrl+C)
        self._setup_sigint_handler()

        self.set_state(AppState.IDLE, "FluidVoice is ready")
        return True

    def _setup_sigint_handler(self) -> None:
        try:
            signal.signal(signal.SIGINT, lambda sig, frame: self.quit())
        except ValueError:
            pass  # Signal only works in main thread

        self.sigint_timer = QTimer(self)
        self.sigint_timer.start(500)
        self.sigint_timer.timeout.connect(lambda: None)

    def set_state(self, state: AppState, message: str = "") -> None:
        """Transitions global application state and updates tray visual indicators."""
        self._state = state
        logger.info(f"App State Changed: {state.name} | {message}")

        tray_state_map = {
            AppState.IDLE: TrayState.IDLE,
            AppState.RECORDING: TrayState.RECORDING,
            AppState.TRANSCRIBING: TrayState.TRANSCRIBING,
            AppState.PASTING: TrayState.TRANSCRIBING,
            AppState.ERROR: TrayState.ERROR,
        }

        if self.tray_icon:
            self.tray_icon.set_state(tray_state_map[state], f"FluidVoice - {message or state.name}")

        self.state_changed.emit(state, message)

    def toggle_recording(self) -> None:
        if self._state == AppState.IDLE:
            self.start_recording()
        elif self._state == AppState.RECORDING:
            self.stop_recording()

    @pyqtSlot()
    def start_recording(self) -> None:
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "start_recording", Qt.ConnectionType.QueuedConnection)
            return

        logger.info("Start recording requested")
        if self.paster_engine:
            self._target_hwnd, _ = self.paster_engine.get_active_window()
        else:
            self._target_hwnd = 0

        if self.overlay_widget:
            self.overlay_widget.set_state("listening", "Listening...")

        self.set_state(AppState.RECORDING, "Listening...")

        if self.audio_recorder:
            success = self.audio_recorder.start_recording()
            if not success:
                self._on_audio_error("Failed to start audio recording stream")

    @pyqtSlot()
    def stop_recording(self) -> bytes:
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "stop_recording", Qt.ConnectionType.QueuedConnection)
            return b""

        logger.info("Stop recording requested")
        if self._state != AppState.RECORDING:
            logger.debug(f"stop_recording called when state is {self._state.name}")
            return b""

        self.set_state(AppState.TRANSCRIBING, "Transcribing...")
        if self.overlay_widget:
            self.overlay_widget.set_state("transcribing", "Transcribing...")

        wav_bytes = b""
        if self.audio_recorder:
            try:
                wav_bytes = self.audio_recorder.stop_recording()
            except Exception as e:
                logger.error(f"Error stopping audio recorder: {e}")
                self._handle_pipeline_error(e)
                return b""

        if wav_bytes and len(wav_bytes) > 44:
            self._process_dictation_pipeline(wav_bytes)

        return wav_bytes

    def _on_audio_level_changed(self, level: float) -> None:
        if self.overlay_widget and self._state == AppState.RECORDING:
            self.overlay_widget.update_audio_level(level)

    def _on_audio_error(self, err_msg: str) -> None:
        logger.error(f"Audio error: {err_msg}")
        self.set_state(AppState.ERROR, f"Error: {err_msg}")
        if self.overlay_widget:
            self.overlay_widget.set_state("error", f"Error: {err_msg}")

    def _process_dictation_pipeline(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            logger.warning("Empty audio bytes received in dictation pipeline")
            self.set_state(AppState.IDLE, "FluidVoice is ready")
            return

        try:
            if self.stt_client is None:
                api_key = self.config_manager.get_api_key()
                if not api_key:
                    raise InvalidAPIKeyError("No Groq API Key configured. Please set your API key in Settings.")
                self.stt_client = GroqSTTClient(
                    api_key=api_key,
                    prompt=self.config_manager.data.hinglish_prompt,
                    language=None,
                )

            sample_rate = self.audio_recorder._sample_rate if self.audio_recorder else 16000
            print(f"[STAGE 1 STT] 📡 Transcribing {len(audio_bytes)} bytes audio via Groq Whisper-v3...")
            raw_text = self.stt_client.transcribe(audio_bytes, sample_rate=sample_rate)
            print(f"[STAGE 1 RAW ASR]: '{raw_text}'")

            if self.post_processor is None:
                self.post_processor = HinglishPostProcessor()

            api_key = self.config_manager.get_api_key() or os.getenv("GROQ_API_KEY", "").strip()
            print("[STAGE 2 LLM] ⚡ Cleaning & formatting via Groq Llama-3.1-8B Instant...")
            processed_text = self.post_processor.process_with_groq_llm(raw_text, api_key=api_key)
            print(f"[STAGE 2 FINAL TEXT]: '{processed_text}'")

            if processed_text and processed_text.strip():
                if self.overlay_widget:
                    self.overlay_widget.set_state("pasted", "Pasted!")
                self.set_state(AppState.PASTING, "Pasted!")

                if self.config_manager.data.auto_paste and self.paster_engine:
                    print(f"[PASTE ENGINE] 📋 Auto-pasting into active cursor location...\n")
                    self.paster_engine.paste_text(processed_text, target_hwnd=self._target_hwnd)

                self.set_state(AppState.IDLE, "FluidVoice is ready")
            else:
                if self.overlay_widget:
                    self.overlay_widget.set_state("idle", "No text transcribed")
                self.set_state(AppState.IDLE, "FluidVoice is ready")

        except Exception as err:
            self._handle_pipeline_error(err)

    def _handle_pipeline_error(self, err: Exception) -> None:
        err_msg = str(err)
        logger.error(f"Pipeline error: {err_msg}")
        self.set_state(AppState.ERROR, f"Error: {err_msg}")
        if self.overlay_widget:
            self.overlay_widget.set_state("error", f"Error: {err_msg}")

    def open_settings(self) -> None:
        logger.info("Open settings dialog requested")
        dialog = SettingsDialog(config_manager=self.config_manager)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, settings_dict: dict) -> None:
        logger.info(f"Settings saved: {settings_dict}")
        if self.hotkey_engine and "hotkey" in settings_dict:
            try:
                self.hotkey_engine.rebind(settings_dict["hotkey"])
            except Exception as e:
                logger.error(f"Failed to rebind hotkey: {e}")

        if self.audio_recorder:
            if "vad_silence_duration_s" in settings_dict:
                self.audio_recorder._silence_duration_sec = float(settings_dict["vad_silence_duration_s"])
            if "max_recording_duration_s" in settings_dict:
                self.audio_recorder._max_duration_sec = float(settings_dict["max_recording_duration_s"])

        api_key = settings_dict.get("groq_api_key") or self.config_manager.get_api_key()
        if api_key:
            try:
                if self.stt_client:
                    self.stt_client.api_key = api_key
                    self.stt_client._headers["Authorization"] = f"Bearer {api_key}"
                else:
                    self.stt_client = GroqSTTClient(api_key=api_key, prompt=self.config_manager.data.hinglish_prompt)
            except Exception as e:
                logger.error(f"Failed to update STT client with new API key: {e}")

    def run(self) -> int:
        if not self.initialize():
            return 1
        logger.info("FluidVoice application event loop started")
        return self.qt_app.exec()

    def quit(self) -> None:
        logger.info("Shutting down FluidVoice...")
        if self.hotkey_engine:
            try:
                self.hotkey_engine.stop()
            except Exception as e:
                logger.warning(f"Failed to stop hotkey engine: {e}")
            self.hotkey_engine = None

        if self.audio_recorder:
            try:
                if self.audio_recorder.is_recording():
                    self.audio_recorder.stop_recording()
            except Exception as e:
                logger.warning(f"Failed to stop audio recorder: {e}")
            self.audio_recorder = None

        if self.overlay_widget:
            try:
                self.overlay_widget.close()
            except Exception as e:
                logger.warning(f"Failed to close overlay widget: {e}")
            self.overlay_widget = None

        if self.tray_icon:
            try:
                self.tray_icon.hide()
            except Exception as e:
                logger.warning(f"Failed to hide tray icon: {e}")
            self.tray_icon = None

        if self.stt_client:
            try:
                self.stt_client.close()
            except Exception as e:
                logger.warning(f"Failed to close STT client: {e}")
            self.stt_client = None

        if self._mutex_handle and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = None
            except Exception as e:
                logger.warning(f"Failed to close Win32 mutex handle: {e}")

        if self._lock_file_path.exists():
            try:
                self._lock_file_path.unlink()
            except Exception:
                pass

        self.qt_app.quit()

