# 🎙️ FluidVoice Windows V1

> **Ultra-Fast, Low-Latency Windows Speech Dictation Software for Roman Hinglish & English**  
> *A high-performance Windows alternative to macOS FluidVoice with zero CPU lag (<100MB RAM) and 100% Roman script output.*

---

## 🌟 Key Features

- **⚡ Two-Stage Groq Pipeline**:
  - **Stage 1 (Groq Whisper-v3-turbo STT)**: Sub-150ms speech-to-text transcription conditioned on Roman Hinglish context.
  - **Stage 2 (Groq Llama-3.1-8B-Instant LLM Engine)**: Sub-100ms non-conversational transliteration & formatting that guarantees 100% Roman Hinglish output (zero Devanagari script leakage) while preserving English technical terms.
- **🎹 Mechanical Keyboard Ergonomic Hotkey (`Alt + S`)**:
  - Designed for comfortable single-hand reach (`Left Thumb + Index Finger`).
  - Immune to Windows Language Switcher popups (`ENG/IN`) and Win-lock modes.
- **✨ Translucent Glassmorphism Overlay UI**:
  - Minimalistic, modern status indicator (`Listening...`, `Transcribing...`, `Pasted!`).
  - GDI-safe layered window rendering with high-DPI scaling.
- **📋 Automatic Cursor Auto-Pasting**:
  - Direct Win32 OLE-safe clipboard injection into active application windows (VS Code, WhatsApp, Notepad, Browser, etc.).
- **🧪 100% Tested & Verified**:
  - Includes comprehensive 4-tier test suite with 207 automated tests.

---

## 📐 Architecture Overview

```
 ┌────────────────────────┐
 │   Press & Hold Alt+S   │
 └───────────┬────────────┘
             │ (Audio Recording via sounddevice)
             ▼
 ┌────────────────────────┐
 │  Groq Whisper-v3-turbo │ ──► Raw Speech Transcription (~150ms)
 └───────────┬────────────┘
             │ (Raw ASR Text)
             ▼
 ┌────────────────────────┐
 │  Groq Llama-3.1-8B     │ ──► Stage 2 Roman Hinglish Cleanup (~100ms)
 └───────────┬────────────┘     (Zero Devanagari Mandate + Technical Term Preservation)
             │ (Clean Roman Hinglish / English Text)
             ▼
 ┌────────────────────────┐
 │ Win32 Auto-Paste Engine│ ──► Pastes directly at active text cursor
 └────────────────────────┘
```

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.11 & 3.14 on Windows 11/10).
- A valid **Groq API Key** (Free tier available at [console.groq.com](https://console.groq.com)).

### 1. Clone & Install Dependencies

```pwsh
git clone https://github.com/rahul-bangle/fluid-voice-windows.git
cd fluid-voice-windows
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Groq API Key

Set your environment variable:
```pwsh
$env:GROQ_API_KEY="your_groq_api_key_here"
```
*Note: FluidVoice will also prompt for your API key on first launch or save it securely via Windows Credential Manager.*

---

## 🚀 Usage

Launch FluidVoice Windows from terminal or PowerShell:

```pwsh
python -m fluid_voice
```

1. Open any target text editor or application (VS Code, WhatsApp, Notepad, Chrome).
2. Press and hold **`Alt + S`** to record your voice.
3. Speak naturally in **English** or **Hinglish** (e.g., *"Haan bhai, code push kar do, meeting 5 baje hai."*).
4. Release **`Alt + S`**. The formatted text will auto-paste at your cursor location in ~300ms!

---

## 🧪 Running the Test Suite

FluidVoice includes 207 tests covering unit behavior, GUI components, Win32 threading, and end-to-end workload pipelines:

```pwsh
python tests/run_tests.py
```

---

## 📁 Project Structure

```text
fluid_voice_windows/
├── fluid_voice/
│   ├── app.py             # Main Application Controller & Qt Threading Loop
│   ├── audio.py           # Sounddevice Audio Recording & VAD Buffer Engine
│   ├── config.py          # Configuration Schema & AppData Persistence
│   ├── hotkey.py          # Pynput Global Hotkey Listener & Win32 Rescue Loop
│   ├── paster.py          # Win32 OLE Clipboard Injector & Auto-Paster
│   ├── post_processor.py  # Stage 2 Groq Llama-3.1-8B LLM Transliteration Engine
│   ├── stt_groq.py        # Stage 1 Groq Whisper-v3 STT Client
│   ├── tray.py            # System Tray Icon & Context Menu
│   └── ui/
│       ├── overlay.py     # Translucent Glassmorphism Status Overlay Widget
│       └── settings_gui.py# Preferences & Configuration Dialog GUI
├── tests/                 # 207 Automated Unit & Integration Tests (Tiers 1-4)
├── requirements.txt       # Project Dependencies
├── .gitignore             # Secrets & Build Artifact Exclusions
└── README.md              # Documentation
```

---

## 📄 License

MIT License. Built for high-speed voice dictation.
