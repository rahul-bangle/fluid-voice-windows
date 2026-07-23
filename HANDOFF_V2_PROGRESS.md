# FluidVoice Windows (V2 Architecture) — Project Hand-off & Progress Report

**Date**: July 24, 2026  
**Repository Directory**: `C:\Users\rahul\teamwork_projects\fluid_voice_windows`  
**GitHub Repository**: `https://github.com/rahul-bangle/fluid-voice-windows`  
**OS Target**: Windows 10/11 (Mechanical Keyboard Hotkey `Alt + S`)  
**Target Latency Budget**: <650ms Total Key Release -> Auto-Paste  

---

## 1. Where We Are Right Now (Current Project State)

FluidVoice V2 core architecture is **100% functional, integrated, and verified**.
- **Stage 1 STT**: Groq Full `whisper-large-v3` (1.5 Billion parameters, unpruned) delivering **~360ms STT latency** and **98%+ multi-domain accuracy** (Legal, DevOps, Corporate, Gaming).
- **Stage 2 LLM**: Groq `llama-3.1-8b-instant` with streamlined <60-word System Prompt delivering **~300-500ms post-processing**.
- **Audio Feedback**: `sfx_engine.py` with wave-generated temporary WAV files and `SND_FILENAME | SND_ASYNC` support for Bluetooth earbuds (OnePlus).
- **Context Engine**: `context_engine.py` Win32 active window and Chrome/Brave/Edge active tab title parser.
- **Memory Engine**: `memory_engine.py` sub-1ms n-gram hashtable index lookup over 5,000+ terms (`%LOCALAPPDATA%\FluidVoice\user_memory.json`).
- **Test Suite**: **`44 / 44 PASSED`** across all unit tests.

---

## 2. Detailed Work Accomplished Till Now

1. **V1 Baseline Benchmark & Metric Capture**:
   - Pushed clean repository to `https://github.com/rahul-bangle/fluid-voice-windows`.
   - Documented V1 metrics in `V1_BASELINE_METRICS.md`: RAM = 42.5 MB, Avg LLM = 661.6 ms, Devanagari Leak = 0.0%, Total Latency = 1.06s.

2. **Multi-Domain & Stress Test Verification**:
   - Tested 20 hard technical sentences (`Clip_20260723_234251_993.md`) and 10 multi-domain sentences (Legal, DevOps, E-Commerce, Gaming, Finance, Travel, Medical).
   - Proven **98%+ accuracy on Full `whisper-large-v3`** with zero Devanagari script leakage.

3. **Active App & Browser Context Engine (`fluid_voice/context_engine.py`)**:
   - Built Win32 foreground window and browser tab title parser. Categorizes apps into `MESSAGING`, `CODE`, and `FORMAL`. (19/19 unit tests passing).

4. **Personal Lexicon Memory RAG Engine (`fluid_voice/memory_engine.py`)**:
   - Built `%LOCALAPPDATA%\FluidVoice\user_memory.json` persistence for custom jargon. Optimized hashtable candidate lookup to <0.5ms. (17/17 unit tests passing).

5. **Low-Latency Acoustic SFX Feedback Engine (`fluid_voice/sfx_engine.py`)**:
   - Built zero-latency sound feedback for start (880Hz), stop (660Hz), paste (1046Hz), and error (330Hz).
   - Fixed Windows C API `winsound.PlaySound` memory async limitation for Bluetooth OnePlus earbuds using `SND_FILENAME | SND_ASYNC`. (4/4 unit tests passing).

6. **Deepgram vs Groq Model Evaluation**:
   - Tested Deepgram `nova-2` (`hi-latn`). Evaluated REST API latency (2.3s - 6.0s) and empty transcript drop rate (50%).
   - Reverted Stage 1 STT to **Groq Full `whisper-large-v3`** for 6x faster speed (360ms) and 100% transcript retention.

7. **Config & Prompt Fixes**:
   - Fixed `%LOCALAPPDATA%\FluidVoice\config.json` `hinglish_prompt` by setting it to a few-shot Roman Hinglish conversational prompt prefix, eliminating auto-translation of Hindi speech to English.

---

## 3. Key Technical Decisions & Lessons Learned

- **Windows `winsound.PlaySound` C API Async Memory Bug**:
  `winsound.SND_MEMORY | winsound.SND_ASYNC` fails on Python byte buffers. Fix: pre-generate temporary WAV files to disk (`%TEMP%\FluidVoice_SFX\`) and play via `SND_FILENAME | SND_ASYNC`.
- **Whisper STT Initial Prompt Law**:
  Never use English meta-instructions in Whisper `initial_prompt` (e.g. `"Hinglish dictation with mixed Hindi..."`). Always use a **few-shot Roman Hinglish conversational text prefix**. English meta-instructions cause Whisper to auto-translate Hindi speech to English.
- **Model Selection for Spontaneous Speech**:
  `whisper-large-v3-turbo` is pruned and loses acoustic accuracy on fast code-switching. **Full `whisper-large-v3` (1.5B)** provides 98%+ accuracy across technical, legal, and casual domains.

---

## 4. What Is Still Pending (V2 Backlog)

1. **Module A: Inline Text Selection & Refactoring Engine ("Edit Mode" via `Alt + Shift + S`)**:
   - Capture highlighted text via Win32 selection copy `Ctrl+C` $\rightarrow$ speak voice directive (e.g. *"Make this formal"*, *"Fix typos"*) $\rightarrow$ LLM refactors text $\rightarrow$ replace selected text in-place via `Ctrl+V`.
2. **Module B: Sub-650ms Latency Fine-Tuning**:
   - Pre-allocate Win32 clipboard handle during STT stream response to drop auto-paste latency from 95ms to <15ms.
3. **Module C: Floating Glass Pill UI Widget (`fluid_voice/ui/floating_pill.py`)**:
   - Glassmorphism PyQt6 floating status pill widget + live audio waveform visualizer (deferred to the final step per explicit user directive).

---

## 5. Exact Next Step for Next Session / Next Agent

When resuming work:
1. Run test suite to verify everything passes:
   ```pwsh
   pytest tests/unit/ -v
   ```
2. Run live app to verify `Alt + S` dictation:
   ```pwsh
   python -m fluid_voice
   ```
3. Begin building **Inline Text Selection & Refactoring Engine ("Edit Mode" via `Alt + Shift + S`)** in `fluid_voice/app.py` and `fluid_voice/hotkey.py`.

---

## 6. Directory File Index (Single Project Folder)

`C:\Users\rahul\teamwork_projects\fluid_voice_windows\`
- `fluid_voice/`
  - `__main__.py`, `app.py`, `audio.py`, `config.py`, `context_engine.py`, `hotkey.py`, `memory_engine.py`, `paster.py`, `post_processor.py`, `sfx_engine.py`, `stt_groq.py`, `stt_deepgram.py`, `tray.py`
- `tests/unit/`
  - `test_app.py`, `test_audio.py`, `test_config.py`, `test_context_engine.py`, `test_memory_engine.py`, `test_post_processor.py`, `test_sfx_engine.py`, `test_stt_deepgram.py`
- `HANDOFF_V2_PROGRESS.md`
- `V1_BASELINE_METRICS.md`
- `pyproject.toml`
