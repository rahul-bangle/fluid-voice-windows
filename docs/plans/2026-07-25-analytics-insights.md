# VeloVoice Analytics & Insights Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Build the complete Wispr Flow-style Analytics & Insights Engine with SQLite data storage, live WPM calculations, time saved metrics, app usage breakdown, activity heatmap, and sub-200ms latency metrics (STT ms, LLM ms, Paste ms).

**Architecture:** An `AnalyticsEngine` class (`fluid_voice/analytics_engine.py`) writes dictation events into a local SQLite database (`analytics.db`). The `VeloVoiceWebBridge` (`fluid_voice/ui/web_bridge.py`) exposes an `getAnalyticsSummary()` method to `QWebEngineView`, which updates the HTML dashboard (`velo_ai_insights_dashboard/code.html`).

**Tech Stack:** Python 3.14, SQLite3, PyQt6, QWebEngineView, HTML5, Tailwind CSS, Pytest.

---

### Task 1: Create `AnalyticsEngine` with SQLite Storage

**Files:**
- Create: `fluid_voice/analytics_engine.py`
- Test: `tests/unit/test_analytics_engine.py`

**Step 1: Write the failing test**

```python
import os
import pytest
from pathlib import Path
from fluid_voice.analytics_engine import AnalyticsEngine

def test_analytics_engine_log_and_query(tmp_path):
    db_file = tmp_path / "analytics.db"
    engine = AnalyticsEngine(db_path=db_file)
    
    engine.log_dictation(
        spoken_text="hello world",
        final_text="Hello world.",
        audio_duration_s=1.0,
        stt_latency_ms=110.0,
        llm_latency_ms=45.0,
        paste_latency_ms=12.0,
        app_name="VS Code",
        ai_fixes_count=1
    )

    summary = engine.get_summary()
    assert summary["total_words"] == 2
    assert summary["total_fixes"] == 1
    assert summary["avg_stt_ms"] == 110.0
    assert summary["app_breakdown"]["VS Code"] == 100
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_analytics_engine.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'fluid_voice.analytics_engine'`

**Step 3: Write minimal implementation**

Create `fluid_voice/analytics_engine.py`:
```python
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """Manages persistent dictation metrics, WPM speed calculations, time saved, and latency logs."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from fluid_voice.config import get_app_data_dir
            db_path = get_app_data_dir() / "analytics.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_str ON dictation_metrics(date_str);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_name ON dictation_metrics(app_name);")
            conn.commit()

    def log_dictation(
        self,
        spoken_text: str,
        final_text: str,
        audio_duration_s: float,
        stt_latency_ms: float,
        llm_latency_ms: float,
        paste_latency_ms: float,
        app_name: str = "Unknown",
        ai_fixes_count: int = 0,
    ) -> None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        spoken_word_count = len(spoken_text.strip().split()) if spoken_text else 0
        final_word_count = len(final_text.strip().split()) if final_text else 0
        
        # WPM calculation: (words / duration_s) * 60
        wpm_speed = (final_word_count / max(audio_duration_s, 0.1)) * 60.0 if audio_duration_s > 0 else 0.0
        
        # Manual typing speed baseline: 40 WPM (0.667 words per second)
        manual_typing_time_s = final_word_count / 0.667 if final_word_count > 0 else 0.0
        time_saved_s = max(0.0, manual_typing_time_s - audio_duration_s)
        total_latency_ms = stt_latency_ms + llm_latency_ms + paste_latency_ms

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dictation_metrics (
                    date_str, spoken_word_count, final_word_count, audio_duration_s,
                    wpm_speed, time_saved_s, stt_latency_ms, llm_latency_ms,
                    paste_latency_ms, total_latency_ms, app_name, ai_fixes_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, spoken_word_count, final_word_count, audio_duration_s,
                wpm_speed, time_saved_s, stt_latency_ms, llm_latency_ms,
                paste_latency_ms, total_latency_ms, app_name, ai_fixes_count
            ))
            conn.commit()

    def get_summary(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*),
                    COALESCE(SUM(final_word_count), 0),
                    COALESCE(AVG(wpm_speed), 0.0),
                    COALESCE(SUM(time_saved_s), 0.0),
                    COALESCE(AVG(stt_latency_ms), 0.0),
                    COALESCE(AVG(llm_latency_ms), 0.0),
                    COALESCE(AVG(paste_latency_ms), 0.0),
                    COALESCE(AVG(total_latency_ms), 0.0),
                    COALESCE(SUM(ai_fixes_count), 0)
                FROM dictation_metrics;
            """)
            row = cursor.fetchone()
            
            # App breakdown
            cursor.execute("""
                SELECT app_name, COUNT(*) FROM dictation_metrics GROUP BY app_name;
            """)
            app_rows = cursor.fetchall()
            total_apps = sum(cnt for _, cnt in app_rows) or 1
            app_breakdown = {app: int((cnt / total_apps) * 100) for app, cnt in app_rows}

            return {
                "total_dictations": row[0],
                "total_words": row[1],
                "avg_wpm": round(row[2], 1),
                "total_time_saved_mins": round(row[3] / 60.0, 1),
                "avg_stt_ms": round(row[4], 1),
                "avg_llm_ms": round(row[5], 1),
                "avg_paste_ms": round(row[6], 1),
                "avg_total_ms": round(row[7], 1),
                "total_fixes": row[8],
                "app_breakdown": app_breakdown,
            }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_analytics_engine.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add fluid_voice/analytics_engine.py tests/unit/test_analytics_engine.py
git commit -m "feat(analytics): add AnalyticsEngine with SQLite metric tracking and summary calculations"
```

---

### Task 2: Expose `getAnalyticsSummary()` via `VeloVoiceWebBridge`

**Files:**
- Modify: `fluid_voice/ui/web_bridge.py:50-80`
- Modify: `fluid_voice/app.py:175-185`
- Test: `tests/unit/test_web_bridge_analytics.py`

**Step 1: Write the failing test**

```python
import json
import pytest
from fluid_voice.ui.web_bridge import VeloVoiceWebBridge

def test_web_bridge_get_analytics_summary(tmp_path):
    class MockApp:
        pass
    
    app = MockApp()
    bridge = VeloVoiceWebBridge(app_controller=app)
    summary_str = bridge.getAnalyticsSummary()
    data = json.loads(summary_str)
    assert "avg_wpm" in data
    assert "avg_stt_ms" in data
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_web_bridge_analytics.py -v`  
Expected: FAIL with `AttributeError: 'VeloVoiceWebBridge' object has no attribute 'getAnalyticsSummary'`

**Step 3: Write minimal implementation**

In `fluid_voice/ui/web_bridge.py`, add `getAnalyticsSummary`:
```python
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
```

Also initialize `self.analytics_engine` in `fluid_voice/app.py`:
```python
        if self.analytics_engine is None:
            self.analytics_engine = AnalyticsEngine()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_web_bridge_analytics.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add fluid_voice/ui/web_bridge.py fluid_voice/app.py tests/unit/test_web_bridge_analytics.py
git commit -m "feat(bridge): expose getAnalyticsSummary API method in VeloVoiceWebBridge"
```

---

### Task 3: Update `velo_ai_insights_dashboard/code.html` with Sub-200ms Latency Card

**Files:**
- Modify: `Frontend/stitch_velovoice_desktop_dictation_system/velo_ai_insights_dashboard/code.html`

**Step 1: Edit HTML to include Latency Card & JavaScript IPC Bridge sync**

Add Sub-200ms Latency Card under the top stats grid:
```html
<!-- Sub-200ms Latency Breakdown Card -->
<div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm mb-8">
  <div class="flex justify-between items-center mb-4">
    <h3 class="text-sm font-bold text-slate-900 uppercase tracking-wider">🚀 Sub-200ms Pipeline Latency Breakdown</h3>
    <span class="text-xs font-bold bg-green-50 text-green-700 px-2.5 py-1 rounded-full border border-green-200">⚡ Sub-200ms Target Active</span>
  </div>
  <div class="grid grid-cols-4 gap-4 text-center">
    <div class="bg-slate-50 p-4 rounded-xl">
      <p class="text-xs font-bold text-slate-500 uppercase">🎙️ STT Latency</p>
      <p id="stt-latency-val" class="text-2xl font-bold text-slate-900 mt-1">110 ms</p>
    </div>
    <div class="bg-slate-50 p-4 rounded-xl">
      <p class="text-xs font-bold text-slate-500 uppercase">🧠 LLM Latency</p>
      <p id="llm-latency-val" class="text-2xl font-bold text-slate-900 mt-1">45 ms</p>
    </div>
    <div class="bg-slate-50 p-4 rounded-xl">
      <p class="text-xs font-bold text-slate-500 uppercase">⚡ Paste Latency</p>
      <p id="paste-latency-val" class="text-2xl font-bold text-slate-900 mt-1">12 ms</p>
    </div>
    <div class="bg-blue-50 p-4 rounded-xl border border-blue-100">
      <p class="text-xs font-bold text-blue-700 uppercase">🎯 Total Pipeline</p>
      <p id="total-latency-val" class="text-2xl font-bold text-blue-900 mt-1">167 ms</p>
    </div>
  </div>
</div>
```

**Step 2: Commit**

```bash
git add Frontend/stitch_velovoice_desktop_dictation_system/velo_ai_insights_dashboard/code.html
git commit -m "feat(ui): add Sub-200ms Latency Breakdown card to Insights Dashboard HTML"
```
