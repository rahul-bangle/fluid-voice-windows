# FluidVoice Windows — Test Infrastructure & Testing Doctrine

## 1. Test Philosophy

FluidVoice Windows adopts a rigorous, **opaque-box (requirement-driven)** test methodology designed to ensure robust execution across diverse Windows desktop environments, low-latency audio capture, secure API credential management, and seamless auto-pasting functionality.

### Core Testing Principles:
1. **Opaque-Box Requirement-Driven Testing**: Tests validate system behavior against specification contracts without relying on private implementation details.
2. **Boundary Value Analysis (BVA)**: Exhaustive testing at equivalence class boundaries (e.g., zero audio duration, maximum 30s audio cap, empty strings, missing config keys, corrupted JSON, network timeouts).
3. **Category-Partition Method**: Systematically decomposing inputs (audio buffers, hotkey keycodes, active window titles, Hinglish phrases) into distinct categories and parameter choices.
4. **Pairwise (Combinatorial) Testing**: Testing representative combinations of OS themes, window types (IDE, browser, terminal), audio input sample rates, and Groq API response states.
5. **Real-World Workload Simulation**: Testing end-to-end user journeys under realistic system conditions (e.g., background noise, multi-language Hinglish dictation, rapid hotkey toggling).

---

## 2. Feature Inventory (9 Core Features)

| # | Feature Subsystem | Module | Description & Critical Test Focus |
|---|-------------------|--------|-----------------------------------|
| 1 | **Config Manager** | `fluid_voice.config` | AppData JSON storage, OS keyring API key security, JSON fallback, environment variable overrides, thread safety. |
| 2 | **Tray Icon & Menu** | `fluid_voice.tray` | Procedural high-DPI badge rendering, state transitions (IDLE, RECORDING, TRANSCRIBING, ERROR), menu action signals. |
| 3 | **Hotkey Listener** | `fluid_voice.hotkey` | Global hotkey listener ('Win+Space', 'Alt+S'), press-to-talk keydown/keyup events, rapid key toggling, hotkey rebinding, thread lifecycle. |
| 4 | **Audio Recorder** | `fluid_voice.audio` | 16kHz mono PCM capture, energy-based VAD silence auto-stop, max duration cap (30s), low-RAM memory buffer management. |
| 5 | **STT Groq Client** | `fluid_voice.stt_groq` | Groq `whisper-large-v3-turbo` API client, zero-shot Hinglish prompt, 401/429/500 HTTP error retry/handling, response parsing. |
| 6 | **Post-Processor** | `fluid_voice.post_processor` | Hinglish normalization, Indian English idiom conversion, Indian currency/lakh/crore formatting, auto-punctuation, capitalization. |
| 7 | **Floating Overlay UI** | `fluid_voice.ui.overlay` | Glassmorphism dark frameless overlay, animated audio waveform, status text updates, non-stealing window focus flag (`WS_EX_NOACTIVATE`). |
| 8 | **Settings GUI** | `fluid_voice.ui.settings` | API key configuration dialog, hotkey binder UI, start-with-windows registry check, test connection button validation. |
| 9 | **Auto-Paster Engine** | `fluid_voice.paster` | Win32 active window focus detection, clipboard backup & restoration, Ctrl+V keyboard injection, terminal/IDE fallback. |

---

## 3. Test Architecture & Pytest Infrastructure

The test suite is structured hierarchically into four distinct tiers:

```
tests/
├── unit/               # Tier 1 & Tier 2: Isolated component & boundary tests
│   ├── test_config.py
│   ├── test_tray.py
│   └── test_hotkey.py
├── integration/        # Tier 3: Cross-subsystem interaction tests
│   ├── test_audio_stt_pipeline.py
│   └── test_app_controller.py
├── e2e/                # Tier 4: Real-world user scenario & workload tests
│   └── test_realworld_workloads.py
├── conftest.py         # Shared Pytest fixtures & mock controllers
└── __init__.py
```

### Shared Mock Fixtures (`conftest.py`):
1. **`qapp`**: Headless PyQt6 `QApplication` instance running with `QT_QPA_PLATFORM=offscreen`.
2. **`mock_audio_stream`**: Sounddevice recorder mock producing valid 16kHz mono 16-bit PCM WAV audio buffers.
3. **`mock_groq_api`**: Interceptor for Groq REST API requests simulating 200 OK, 401 Unauthorized, 429 Rate Limit, and 500 Error responses.
4. **`mock_win32_paster`**: Win32 window handle and clipboard auto-paster mock for focus and pasting verification.
5. **`hinglish_test_dataset`**: Standardized test corpus containing Hinglish phrases, Indian English idioms, number formatting, and boundary cases.

---

## 4. Real-World Application Scenarios (Tier 4 Specs)

| Scenario ID | Application Context | Input & Conditions | Expected System Behavior |
|-------------|---------------------|--------------------|--------------------------|
| **SC-01** | VS Code / PyCharm IDE Dictation | Dictating code logic with mixed English & Hindi: `"def calculate total function me error handler add karo"` | Formats identifiers (`calculate_total`), preserves code context, pastes at active cursor without losing IDE focus. |
| **SC-02** | Slack / Teams Chat Message | Fast dictation: `"bhai please prepone the meeting to 3 PM"` | Normalizes idiom (`"Bhai, please reschedule the meeting to 3:00 PM."`), pastes directly into active chat text field. |
| **SC-03** | Long Document Dictation | Multi-sentence input (25s audio) with currency: `"the company revenue crossed 10 crore rupees this year"` | Formats currency (`"Rs 100,000,000"`), auto-punctuates sentences, handles maximum audio buffer gracefully. |
| **SC-04** | High Ambient Noise / Silence | User presses hotkey, hesitates for 2s in quiet room, then speaks | VAD ignores initial silence, captures speech, auto-stops when silence returns after speech. |
| **SC-05** | Rapid Hotkey Toggling | User presses `Win+Space` 10 times in 1 second | Debouncing logic prevents race conditions, thread state remains consistent, no double recording triggers. |

---

## 5. Coverage & Quality Thresholds

- **Tier 1 (Happy Path Feature Coverage)**: Minimum **>= 5 test cases per feature** across all 9 subsystems.
- **Tier 2 (Boundary & Corner Cases)**: Minimum **>= 5 boundary cases per feature** (empty inputs, corrupted data, network errors, invalid key combinations, thread safety).
- **Tier 3 (Integration Tests)**: Cross-subsystem workflow verification (Hotkey -> Audio -> STT -> Post-Processor -> Paster).
- **Tier 4 (Real-World Scenarios)**: E2E workload simulation passing 100% of defined scenarios.
- **Minimum Test Suite Requirement**: Minimum **10 tests per unit test file** in `tests/unit/`.
