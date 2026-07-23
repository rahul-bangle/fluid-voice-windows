# Project: FluidVoice Windows

## Architecture
FluidVoice is a lightweight Windows dictation tool built in Python using PyQt6, sounddevice, Groq Whisper REST API, and Win32/pyautogui pasting APIs.

### Key Modules:
- `fluid_voice.config`: Config loader/saver, keyring/JSON secure storage for Groq API key, hotkey settings.
- `fluid_voice.tray`: PyQt6 System Tray icon & menu management.
- `fluid_voice.hotkey`: Global key listener (`pynput`/`keyboard`) for press-to-talk (`Win+Space` / `Alt+S`).
- `fluid_voice.audio`: `sounddevice` low-RAM audio recorder with silence detection VAD and duration cap.
- `fluid_voice.stt_groq`: Groq API client utilizing `whisper-large-v3-turbo` with Hinglish zero-shot prompt.
- `fluid_voice.post_processor`: Hinglish text normalizer, auto-punctuation, capitalization, number/date formatting, Indian English idiom handler.
- `fluid_voice.ui.overlay`: Glassmorphism dark frameless floating widget with animated waveform and status messages.
- `fluid_voice.ui.settings`: Setup & settings dialog for API key setup and configuration.
- `fluid_voice.paster`: Active window focus detector and keyboard/clipboard text injector.
- `fluid_voice.app`: Controller gluing all components together.

## Code Layout
```
C:\Users\rahul\teamwork_projects\fluid_voice_windows\
├── fluid_voice\
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── config.py
│   ├── tray.py
│   ├── hotkey.py
│   ├── audio.py
│   ├── stt_groq.py
│   ├── post_processor.py
│   ├── paster.py
│   └── ui\
│       ├── __init__.py
│       ├── overlay.py
│       └── settings.py
├── tests\
│   ├── unit\
│   ├── integration\
│   └── e2e\
├── requirements.txt
├── README.md
└── pyproject.toml
```

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core App Framework & System Tray | config.py, tray.py, app.py shell | None | DONE |
| M2 | Global Hotkey Engine & Audio Capture | hotkey.py, audio.py | M1 | DONE |
| M3 | Groq Whisper STT Client | stt_groq.py | M1 | DONE |
| M4 | Hinglish Post-Processor | post_processor.py | M1 | DONE |
| M5 | Sleek Minimal Floating Overlay UI | ui/overlay.py | M1 | DONE |
| M6 | Settings GUI & Auto-Paster Engine | ui/settings.py, paster.py | M1 | DONE |
| M7 | Integration & Performance Verification | E2E assembly, perf audit, 100% test pass | M1-M6 | DONE |

## Interface Contracts
### `stt_groq` ↔ `post_processor`
- `STTClient.transcribe(audio_bytes: bytes, sample_rate: int) -> str`
- `HinglishPostProcessor.process(raw_text: str) -> str`

### `audio` ↔ `stt_groq`
- `AudioRecorder.stop_recording() -> bytes` (WAV format, 16kHz mono 16-bit PCM)

### `app` ↔ `paster`
- `AutoPaster.paste_text(text: str) -> bool`

### `app` ↔ `ui.overlay`
- `OverlayWidget.set_state(state: str, message: str)` ('listening', 'transcribing', 'pasted', 'error')
- `OverlayWidget.update_audio_level(level: float)`
