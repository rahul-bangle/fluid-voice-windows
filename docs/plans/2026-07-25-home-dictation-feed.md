# VeloVoice Home Dictation Feed Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Wire live dynamic dictation history into the Home Feed (`velo_ai_dashboard_light_mode/code.html`) displaying timestamps, target app badges, transcribed sentences, and 1-click copy/delete actions.

**Architecture:** `VeloVoiceWebBridge.getHistory()` reads dictation history items from `analytics.db` / `dictation_metrics`. The JavaScript in `velo_ai_dashboard_light_mode/code.html` renders these entries dynamically grouped by date with 1-click clipboard copy.

**Tech Stack:** Python 3.14, SQLite3, PyQt6, QWebEngineView, HTML5, JavaScript, Tailwind CSS.

---

### Task 1: Extend `AnalyticsEngine` & `VeloVoiceWebBridge` to return formatted history entries

**Files:**
- Modify: `fluid_voice/analytics_engine.py:80-120`
- Modify: `fluid_voice/ui/web_bridge.py:20-40`
- Test: `tests/unit/test_analytics_history.py`

**Step 1: Write the failing test**

```python
import pytest
from fluid_voice.analytics_engine import AnalyticsEngine

def test_analytics_engine_get_recent_history(tmp_path):
    db_file = tmp_path / "analytics.db"
    engine = AnalyticsEngine(db_path=db_file)
    
    engine.log_dictation(
        spoken_text="test sentence",
        final_text="Test sentence.",
        audio_duration_s=1.5,
        stt_latency_ms=100.0,
        llm_latency_ms=40.0,
        paste_latency_ms=10.0,
        app_name="VS Code",
        ai_fixes_count=0
    )

    history = engine.get_recent_history(limit=10)
    assert len(history) == 1
    assert history[0]["final_text"] == "Test sentence."
    assert history[0]["app_name"] == "VS Code"
    assert "time_str" in history[0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_analytics_history.py -v`  
Expected: FAIL with `AttributeError: 'AnalyticsEngine' object has no attribute 'get_recent_history'`

**Step 3: Write minimal implementation**

In `fluid_voice/analytics_engine.py`:
```python
    def get_recent_history(self, limit: int = 50) -> list:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, date_str, spoken_text, final_text, app_name, wpm_speed
                FROM dictation_metrics
                ORDER BY id DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            history = []
            for r in rows:
                dt_str = r[1]
                try:
                    time_str = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p")
                except Exception:
                    time_str = dt_str
                history.append({
                    "id": r[0],
                    "timestamp": r[1],
                    "date_str": r[2],
                    "spoken_text": r[3],
                    "final_text": r[4],
                    "app_name": r[5],
                    "wpm_speed": round(r[6], 1),
                    "time_str": time_str,
                })
            return history
```

In `fluid_voice/ui/web_bridge.py`:
```python
    @pyqtSlot(result=str)
    def getHistory(self) -> str:
        """Returns JSON list of past dictation history items."""
        if not self.app or not getattr(self.app, "analytics_engine", None):
            return json.dumps([])
        try:
            history = self.app.analytics_engine.get_recent_history(limit=50)
            return json.dumps(history)
        except Exception as e:
            logger.error(f"Failed to get history for WebBridge: {e}")
            return json.dumps([])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_analytics_history.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add fluid_voice/analytics_engine.py fluid_voice/ui/web_bridge.py tests/unit/test_analytics_history.py
git commit -m "feat(history): add get_recent_history method to AnalyticsEngine and wire to WebBridge"
```

---

### Task 2: Dynamically render Home Feed in `velo_ai_dashboard_light_mode/code.html`

**Files:**
- Modify: `Frontend/stitch_velovoice_desktop_dictation_system/velo_ai_dashboard_light_mode/code.html`

**Step 1: Add dynamic JS renderer to populate feed on page load**

Add script block at end of `code.html`:
```html
<script>
  document.addEventListener("DOMContentLoaded", function() {
    if (window.pyqtBridge) {
      try {
        var historyJson = window.pyqtBridge.getHistory();
        var historyData = JSON.parse(historyJson);
        renderHistoryFeed(historyData);
      } catch(e) {
        console.error("Failed to load history:", e);
      }
    }
  });

  function renderHistoryFeed(items) {
    var feedContainer = document.querySelector('[data-purpose="recent-activity"]');
    if (!feedContainer || !items || items.length === 0) return;
    
    var html = '<div class="bg-white rounded-2xl border border-brand-border divide-y divide-brand-border shadow-sm overflow-hidden">';
    items.forEach(function(item) {
      html += `
        <div class="p-6 flex items-start space-x-6 hover:bg-gray-50 transition-colors group">
          <div class="flex flex-col items-start min-w-[70px]">
            <span class="text-xs font-medium text-brand-muted whitespace-nowrap">${item.time_str || ''}</span>
            <span class="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded mt-1">${item.app_name || 'Desktop'}</span>
          </div>
          <div class="flex-1">
            <p class="text-brand-text leading-relaxed font-medium">${escapeHtml(item.final_text)}</p>
          </div>
          <div class="flex items-center space-x-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onclick="navigator.clipboard.writeText('${escapeJs(item.final_text)}')" class="p-1.5 text-brand-muted hover:text-brand-primary hover:bg-white rounded-lg border border-transparent hover:border-brand-border shadow-sm" title="Copy to clipboard">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
            </button>
          </div>
        </div>
      `;
    });
    html += '</div>';
    feedContainer.innerHTML = html;
  }
</script>
```

**Step 2: Commit**

```bash
git add Frontend/stitch_velovoice_desktop_dictation_system/velo_ai_dashboard_light_mode/code.html
git commit -m "feat(ui): add dynamic Home Feed rendering and 1-click copy to code.html"
```
