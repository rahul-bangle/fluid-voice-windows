# 📊 VeloVoice Analytics & Insights Engine Design

## Overview
The VeloVoice Analytics & Insights Engine provides comprehensive usage metrics, typing speed calculations, time saved analytics, app-by-app usage breakdown, daily activity streak heatmaps, and real-time sub-200ms latency metrics (STT ms, LLM ms, Paste ms).

---

## 🗄️ Architecture & Data Model

### Database Location
`AppData/Local/FluidVoice/analytics.db`

### SQLite Schema (`dictation_metrics`)
```sql
CREATE TABLE IF NOT EXISTS dictation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_str TEXT NOT NULL,
    spoken_word_count INTEGER NOT NULL,
    final_word_count INTEGER NOT NULL,
    audio_duration_s REAL NOT NULL,
    wpm_speed REAL NOT NULL,
    time_saved_s REAL NOT NULL,
    stt_latency_ms REAL NOT NULL,
    llm_latency_ms REAL NOT NULL,
    paste_latency_ms REAL NOT NULL,
    total_latency_ms REAL NOT NULL,
    app_name TEXT NOT NULL,
    ai_fixes_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_date_str ON dictation_metrics(date_str);
CREATE INDEX IF NOT EXISTS idx_app_name ON dictation_metrics(app_name);
```

---

## 🎨 UI Component Architecture

### Frontend View
`Frontend/stitch_velovoice_desktop_dictation_system/velo_ai_insights_dashboard/code.html`

### Key UI Sections
1. **WPM Speed Gauge Card**: Spoken typing speed (e.g. 295 WPM) vs 40 WPM manual baseline.
2. **Sub-200ms Latency Metrics Card**: Live meters for STT latency (ms), LLM latency (ms), Paste latency (ms), and Total pipeline latency (ms).
3. **AI Fixes & Corrections Card**: Count of words auto-corrected by Llama-3.1 & phonetic engine.
4. **Total Words & Time Saved Card**: Total words dictated + Hours/Minutes saved counter.
5. **App Usage Breakdown**: Percentage breakdown by target window context (`VS Code`, `Telegram`, `Terminal`, `Browser`).
6. **Activity Streak Heatmap**: Calendar grid showing daily activity dots and streak count.

---

## 🔌 IPC Bridge Interface (`fluid_voice/ui/web_bridge.py`)

```python
@pyqtSlot(result=str)
def getAnalyticsSummary(self) -> str:
    """Returns aggregated JSON payload for the Insights HTML Dashboard."""
```

### JSON Data Payload
```json
{
  "avg_wpm": 295.0,
  "total_words": 1420,
  "total_time_saved_mins": 35.2,
  "total_fixes": 42,
  "avg_stt_ms": 112.0,
  "avg_llm_ms": 48.0,
  "avg_paste_ms": 14.0,
  "avg_total_ms": 174.0,
  "app_breakdown": {
    "VS Code": 65,
    "Telegram": 20,
    "Windows Terminal": 15
  },
  "current_streak": 7,
  "daily_heatmap": {"2026-07-25": 142, "2026-07-24": 98}
}
```
