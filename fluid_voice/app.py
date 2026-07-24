import os
import sys
import time
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
from fluid_voice.post_processor import HinglishPostProcessor, parse_spoken_action
from fluid_voice.ui.overlay import OverlayWidget
from fluid_voice.ui.settings import SettingsDialog
from fluid_voice.paster import AutoPaster
from fluid_voice.context_engine import ContextEngine, AppContext
from fluid_voice.memory_engine import MemoryEngine
from fluid_voice.sfx_engine import SFXEngine

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
    ContextEngine, OverlayWidget, AutoPaster, SystemTrayIcon, and SettingsDialog.
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
        self._is_jarvis_mode: bool = False
        self._target_hwnd = 0
        self._current_context: AppContext | None = None
        self._last_raw_transcript: str = ""
        self._last_transcript: str = ""

        # Core Subsystems
        self.config_manager = ConfigManager(config_dir=config_dir)
        self.tray_icon: FluidVoiceTrayIcon | None = None
        self.hotkey_engine: HotkeyListener | None = None
        self.audio_recorder: AudioRecorder | None = None
        self.stt_client: GroqSTTClient | None = None
        self.post_processor: HinglishPostProcessor | None = None
        self.context_engine: ContextEngine | None = ContextEngine()
        self.overlay_widget: OverlayWidget | None = None
        self.paster_engine: AutoPaster | None = None
        self.memory_engine: MemoryEngine | None = None

    @property
    def current_state(self) -> AppState:
        return self._state

    @property
    def is_jarvis_mode(self) -> bool:
        return self._is_jarvis_mode

    @pyqtSlot()
    def toggle_jarvis_mode(self) -> None:
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "toggle_jarvis_mode", Qt.ConnectionType.QueuedConnection)
            return

        if self.hotkey_engine:
            self.hotkey_engine.toggle_jarvis_mode()

        self._is_jarvis_mode = not self._is_jarvis_mode
        self._jarvis_active = False  # Starts in STANDBY mode to ignore background noise
        mode_name = "Jarvis Hands-Free Mode" if self._is_jarvis_mode else "Push-To-Talk Mode"
        logger.info(f"Toggled mode: {mode_name}")

        if self.audio_recorder:
            self.audio_recorder.is_jarvis_mode = self._is_jarvis_mode
            if self._is_jarvis_mode:
                try:
                    self.audio_recorder.speech_chunk_emitted.disconnect(self._on_jarvis_speech_chunk)
                except Exception:
                    pass
                self.audio_recorder.speech_chunk_emitted.connect(self._on_jarvis_speech_chunk)
                if not self.audio_recorder.is_recording():
                    self.start_recording()

        if self.tray_icon:
            state = TrayState.RECORDING if self._is_jarvis_mode else TrayState.IDLE
            self.tray_icon.set_state(state, f"FluidVoice - {mode_name}")

        if self.overlay_widget:
            if self._is_jarvis_mode:
                self.overlay_widget.set_state("listening", "JARVIS STANDBY 🟡 (Say 'Type' to start)")
            else:
                self.overlay_widget.set_state("idle", "Push-To-Talk Mode")

    @pyqtSlot(bytes)
    def _on_jarvis_speech_chunk(self, wav_bytes: bytes) -> None:
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "_on_jarvis_speech_chunk", Qt.ConnectionType.QueuedConnection, pyqtSlot(bytes)(wav_bytes))
            return
        if wav_bytes and len(wav_bytes) > 44:
            self._process_dictation_pipeline(wav_bytes)

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

        # Initialize Memory Engine
        if self.memory_engine is None:
            self.memory_engine = MemoryEngine(filepath=self.config_manager.config_dir / "user_memory.json")

        # Initialize SFX Engine
        if not hasattr(self, "sfx_engine") or self.sfx_engine is None:
            self.sfx_engine = SFXEngine(enabled=getattr(self.config_manager.data, "sfx_enabled", True))

        # Initialize Post Processor
        if self.post_processor is None:
            self.post_processor = HinglishPostProcessor()
        if self.memory_engine:
            self.post_processor.update_brand_map(self.memory_engine.get_phonetic_mappings())

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
                    language=getattr(self.config_manager.data, "language", "en"),
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
        self.hotkey_engine.add_hotkey("Ctrl+Alt+C", on_keydown=self.learn_from_clipboard)
        self.hotkey_engine.add_hotkey("Alt+Shift+J", on_keydown=self.toggle_jarvis_mode)
        self.hotkey_engine.add_hotkey("esc", on_keydown=self.cancel_recording)
        if not self.hotkey_engine.is_running:
            self.hotkey_engine.start()

        # Initialize Habit-Breaking Voice Nudge Engine
        if not hasattr(self, "habit_nudge") or self.habit_nudge is None:
            from fluid_voice.habit_nudge import HabitNudgeEngine
            self.habit_nudge = HabitNudgeEngine(
                key_threshold=5,
                on_nudge_trigger=self._on_habit_nudge_triggered,
                is_pasting_check=lambda: self._state != AppState.IDLE,
            )
            self.habit_nudge.start()

        # Wire Python signal handler for clean CLI termination (Ctrl+C)
        self._setup_sigint_handler()

        self.set_state(AppState.IDLE, "VeloVoice is ready")

        # Play startup chime & show launch toast notification
        if hasattr(self, "sfx_engine") and self.sfx_engine:
            self.sfx_engine.play("startup")

        if self.overlay_widget:
            self.overlay_widget.show_toast("⚡ VeloVoice Ready! Hold Alt+S", duration_ms=2500)

        return True

    @pyqtSlot()
    def _on_habit_nudge_triggered(self) -> None:
        """Triggered when user types > 5 manual keys to remind them of VeloVoice voice typing."""
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "_on_habit_nudge_triggered", Qt.ConnectionType.QueuedConnection)
            return

        logger.info("[HABIT NUDGE] Showing voice typing reminder toast.")
        if self.overlay_widget:
            self.overlay_widget.show_toast("💡 Save time! Press Alt+S for voice typing", duration_ms=2500)

    def _setup_sigint_handler(self) -> None:
        try:
            signal.signal(signal.SIGINT, lambda sig, frame: self.quit())
        except ValueError:
            pass  # Signal only works in main thread

        self.sigint_timer = QTimer(self)
        self.sigint_timer.start(500)
        self.sigint_timer.timeout.connect(lambda: None)

    def set_state(self, state: AppState, message: str = "") -> None:
        """Transitions global application state and updates tray and overlay visual indicators."""
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

        if self.overlay_widget:
            overlay_map = {
                AppState.IDLE: "idle",
                AppState.RECORDING: "listening",
                AppState.TRANSCRIBING: "transcribing",
                AppState.PASTING: "pasted",
                AppState.ERROR: "error",
            }
            if state in overlay_map:
                self.overlay_widget.set_state(overlay_map[state], message or state.name)

        self.state_changed.emit(state, message)

    @pyqtSlot()
    def cancel_recording(self) -> None:
        """Emergency ESC hatch: Aborts active recording/transcription, clears audio, and hides overlay."""
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "cancel_recording", Qt.ConnectionType.QueuedConnection)
            return

        logger.info("[EMERGENCY CANCEL] ESC key pressed. Aborting recording and clearing audio buffer.")
        if self.audio_recorder and self.audio_recorder.is_recording():
            try:
                self.audio_recorder.stop_recording()
            except Exception:
                pass
        self._last_raw_transcript = ""
        self.set_state(AppState.IDLE, "FluidVoice is ready")

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
        if hasattr(self, "habit_nudge") and self.habit_nudge:
            self.habit_nudge.reset_nudge_state()

        if self.paster_engine:
            self._target_hwnd, _ = self.paster_engine.get_active_window()
        else:
            self._target_hwnd = 0

        if self.context_engine:
            try:
                self._current_context = self.context_engine.get_active_context()
            except Exception as e:
                logger.warning(f"Failed to capture context: {e}")
                self._current_context = None

        if self.overlay_widget:
            self.overlay_widget.set_state("listening", "Listening...")

        self.set_state(AppState.RECORDING, "Listening...")

        if hasattr(self, "sfx_engine") and self.sfx_engine:
            self.sfx_engine.play("start")

        if self.audio_recorder:
            success = self.audio_recorder.start_recording()
            if not success:
                self._on_audio_error("Failed to start audio recording stream")

    @pyqtSlot()
    def stop_recording(self) -> bytes:
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "stop_recording", Qt.ConnectionType.QueuedConnection)
            return b""

        if hasattr(self, "sfx_engine") and self.sfx_engine:
            self.sfx_engine.play("stop")

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
        """Executes the STT transcription and post-processing pipeline with rate-limit and latency guards."""
        t_pipeline_start = time.perf_counter()
        if not audio_bytes or len(audio_bytes) < 8000:
            logger.debug("Audio chunk too short (<0.25s). Skipping pipeline.")
            if self.hotkey_engine and getattr(self.hotkey_engine, "mode", "") == "jarvis":
                self.set_state(AppState.RECORDING, "Jarvis Standby")
            else:
                self.set_state(AppState.IDLE, "FluidVoice is ready")
            return

        try:
            sample_rate = self.audio_recorder._sample_rate if self.audio_recorder else 16000
            t_stt_start = time.perf_counter()

            force_offline = (
                os.getenv("FORCE_OFFLINE", "0").strip() in ("1", "true", "True")
                or getattr(self.config_manager.data, "force_offline_mode", False)
                or getattr(self.config_manager.data, "use_fast_local_engine", False)
            )

            raw_text = None
            if self.stt_client is not None and not force_offline:
                try:
                    print(f"[STAGE 1 STT] 📡 Transcribing {len(audio_bytes)} bytes audio via Groq Whisper-v3...")
                    raw_text = self.stt_client.transcribe(audio_bytes, sample_rate=sample_rate)
                except Exception as cloud_err:
                    logger.warning(f"[CIRCUIT BREAKER TRIGGERED] Groq STT cloud request failed ({cloud_err}). Failing over to Local STT...")

            if not raw_text:
                from fluid_voice.stt_local import LocalWhisperSTTClient
                if not hasattr(self, "local_stt_client") or self.local_stt_client is None:
                    self.local_stt_client = LocalWhisperSTTClient()
                print(f"[STAGE 1 LOCAL STT] ⚡ Transcribing via Local Offline STT Fallback (faster-whisper small INT8)...")
                raw_text = self.local_stt_client.transcribe_audio_bytes(
                    audio_bytes,
                    prompt=self.config_manager.data.hinglish_prompt if self.config_manager else None,
                )

            self._last_raw_transcript = raw_text or ""

            t_stt_done = time.perf_counter()
            stt_latency_ms = (t_stt_done - t_stt_start) * 1000.0
            print(f"[STAGE 1 RAW ASR] ({stt_latency_ms:.1f} ms): '{raw_text}'")

            if self.post_processor is None:
                self.post_processor = HinglishPostProcessor()

            raw_lower = (raw_text or "").strip().lower()

            # Fast Pre-Filter 1: Standby Mode Audio Gate (Bypasses LLM to prevent rate limits)
            if self.hotkey_engine and getattr(self.hotkey_engine, "mode", "") == "jarvis":
                from fluid_voice.post_processor import parse_jarvis_trigger
                is_active = getattr(self, "_jarvis_active", False)
                cleaned_j_text, new_active_state, j_status = parse_jarvis_trigger(raw_text, is_active)
                self._jarvis_active = new_active_state

                if j_status == "ACTIVATED":
                    if self.overlay_widget:
                        self.overlay_widget.set_state("recording", "JARVIS ACTIVE 🟢 Dictating...")
                    print("\n[JARVIS STATUS] 🟢 Callout trigger detected ('Type') -> Activated typing!")
                elif j_status == "PAUSED":
                    if self.overlay_widget:
                        self.overlay_widget.set_state("listening", "JARVIS STANDBY 🟡 Paused")
                    print("\n[JARVIS STATUS] 🟡 Pause trigger detected ('Jarvis Pause') -> Standby mode!")
                elif j_status == "IGNORED":
                    print("[JARVIS STATUS] 🔇 Background noise ignored while in Standby Mode.")
                    self.set_state(AppState.RECORDING, "Jarvis Standby")
                    return

                raw_text = cleaned_j_text
                raw_lower = (raw_text or "").strip().lower()

            # Fast Pre-Filter 2: Whisper Hallucination & Silence Guard (Strips tail hallucinations)
            cleaned_raw = self.post_processor.clean_hallucinations(raw_text) if self.post_processor else raw_text
            if not cleaned_raw or not cleaned_raw.strip():
                print("[STAGE 2 LLM] ⏭️ Skipping Stage 2 LLM for empty/hallucinated transcript.")
                self.set_state(AppState.IDLE, "FluidVoice is ready")
                return

            raw_text = cleaned_raw
            raw_lower = raw_text.lower()

            api_key = self.config_manager.get_api_key() or os.getenv("GROQ_API_KEY", "").strip()
            t_llm_start = time.perf_counter()

            if force_offline:
                print("[STAGE 2 LOCAL] ⚡ Ultra-fast sub-millisecond local rule engine active (100% Offline Mode)...")
                processed_text = self.post_processor.process(raw_text)
            else:
                print("[STAGE 2 LLM] ⚡ Cleaning & formatting via Groq Llama-3.1-8B Instant...")
                try:
                    processed_text = self.post_processor.process_with_groq_llm(
                        raw_text, api_key=api_key, context=self._current_context, memory_engine=self.memory_engine
                    )
                except Exception as llm_err:
                    logger.warning(f"Stage 2 LLM unavailable ({llm_err}). Falling back to fast deterministic rule engine.")
                    processed_text = self.post_processor.process(raw_text)

            cleaned_text, action = parse_spoken_action(processed_text)
            self._last_transcript = cleaned_text or processed_text or ""
            t_llm_done = time.perf_counter()
            llm_latency_ms = (t_llm_done - t_llm_start) * 1000.0
            print(f"[STAGE 2 FINAL TEXT] ({llm_latency_ms:.1f} ms): '{cleaned_text}' (Action: {action})")

            if (cleaned_text and cleaned_text.strip()) or action:
                if self.overlay_widget:
                    self.overlay_widget.set_state("pasted", "Pasted!")
                self.set_state(AppState.PASTING, "Pasted!")

                t_paste_start = time.perf_counter()
                if self.config_manager.data.auto_paste and self.paster_engine:
                    if action:
                        self.paster_engine.paste_text_and_execute_action(cleaned_text, action=action, target_hwnd=self._target_hwnd)
                    else:
                        self.paster_engine.paste_text(cleaned_text, target_hwnd=self._target_hwnd)
                t_paste_done = time.perf_counter()
                paste_latency_ms = (t_paste_done - t_paste_start) * 1000.0

                total_processing_ms = (t_paste_done - getattr(self, '_t_key_release', t_pipeline_start)) * 1000.0
                mode_str = "100% LOCAL OFFLINE" if force_offline else "HYBRID CLOUD"
                print(f"\n=================== [{mode_str} LATENCY METRICS SUMMARY] ===================")
                print(f"  • Stage 1 STT Latency ({'faster-whisper small INT8' if force_offline else 'Groq Whisper Turbo'}) : {stt_latency_ms:.1f} ms")
                print(f"  • Stage 2 LLM/Rule Cleanup Latency                         : {llm_latency_ms:.1f} ms")
                print(f"  • Win32 Direct SendInput Injection Latency                : {paste_latency_ms:.1f} ms")
                print(f"  • TOTAL KEY RELEASE -> AUTO-PASTE                         : {total_processing_ms:.1f} ms")
                print("=========================================================================\n")

                if hasattr(self, "sfx_engine") and self.sfx_engine:
                    self.sfx_engine.play("paste")

                # Snapshot for Phase 2: Autonomous 5-Second Post-Paste Auto-Learning Engine
                self._last_paste_snapshot = (cleaned_text, raw_text, time.time())
                QTimer.singleShot(5000, self._check_passive_learning_snapshot)

                self.set_state(AppState.IDLE, "FluidVoice is ready")
            else:
                if self.overlay_widget:
                    self.overlay_widget.set_state("idle", "No text transcribed")
                self.set_state(AppState.IDLE, "FluidVoice is ready")

        except Exception as err:
            if hasattr(self, "sfx_engine") and self.sfx_engine:
                self.sfx_engine.play("error")
            self._handle_pipeline_error(err)

    @pyqtSlot()
    def learn_from_clipboard(self, corrected_text: Optional[str] = None) -> Optional[MemoryItem]:
        """
        Captures active clipboard text upon Ctrl+Alt+C hotkey press and executes
        word-level token diffing against self._last_raw_transcript to learn terms.
        """
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "learn_from_clipboard", Qt.ConnectionType.QueuedConnection)
            return None

        if corrected_text is None:
            try:
                clipboard = self.qt_app.clipboard()
                corrected_text = clipboard.text() if clipboard else ""
            except Exception as e:
                logger.warning(f"Failed to read clipboard text: {e}")
                corrected_text = ""

        if not corrected_text or not corrected_text.strip():
            logger.warning("Clipboard is empty or contains no text for correction learning.")
            return None

        clean_corr = corrected_text.strip()
        # Ignore file paths, URLs, or command lines copied to clipboard
        if clean_corr.lower().startswith(("c:\\", "e:\\", "d:\\", "http://", "https://", "file://", "ps ")) or (len(clean_corr) > 2 and clean_corr[1:3] == ":\\"):
            logger.warning(f"Clipboard contains a file path or URL ('{clean_corr}'). Skipping memory learning.")
            return None

        spoken_text = getattr(self, "_last_raw_transcript", "") or getattr(self, "_last_transcript", "")
        if not spoken_text:
            logger.warning("No previous transcript available to compare with correction.")
            return None

        if not self.memory_engine:
            self.memory_engine = MemoryEngine(filepath=self.config_manager.config_dir / "user_memory.json")

        item = self.memory_engine.learn_from_correction(
            spoken_text=spoken_text,
            corrected_term=corrected_text,
            context=self._current_context,
        )

        if item and self.post_processor:
            self.post_processor.update_brand_map(self.memory_engine.get_phonetic_mappings())

        logger.info(f"Learned correction from clipboard: '{spoken_text}' -> '{corrected_text}'")
        return item

    @pyqtSlot()
    def _check_passive_learning_snapshot(self) -> None:
        """
        Phase 2: Autonomous 5-Second Post-Paste Auto-Learning Engine.
        Queries on-screen active window caret text snippet directly.
        BANS system clipboard reads (clipboard reads reserved strictly for Ctrl+Alt+C).
        """
        if not hasattr(self, "_last_paste_snapshot") or not self._last_paste_snapshot:
            return
        pasted_text, raw_text, t_paste = self._last_paste_snapshot
        self._last_paste_snapshot = None

        try:
            if not self.paster_engine:
                return

            caret_snippet = self.paster_engine.get_active_caret_text()
            if not caret_snippet or not caret_snippet.strip():
                return

            spoken_text = raw_text or pasted_text
            if spoken_text and caret_snippet != pasted_text:
                if not self.memory_engine:
                    self.memory_engine = MemoryEngine(filepath=self.config_manager.config_dir / "user_memory.json")

                item = self.memory_engine.learn_from_correction(
                    spoken_text=spoken_text,
                    corrected_term=caret_snippet,
                    context=self._current_context,
                )
                if item and self.post_processor:
                    self.post_processor.update_brand_map(self.memory_engine.get_phonetic_mappings())
                    logger.info(f"[PASSIVE UIA LEARNING] Learned true acoustic mishear from caret: '{spoken_text}' -> '{caret_snippet}'")
        except Exception as e:
            logger.debug(f"Passive UIA learning snapshot check skipped: {e}")

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
                    self.stt_client = GroqSTTClient(
                        api_key=api_key,
                        prompt=self.config_manager.data.hinglish_prompt,
                        language=getattr(self.config_manager.data, "language", "en"),
                    )
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

    def __del__(self):
        if hasattr(self, "_mutex_handle") and self._mutex_handle and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = None
            except Exception:
                pass

