"""
fluid_voice.analytics_engine: Manages persistent dictation metrics, WPM speed calculations,
time saved analytics, app usage breakdown, and sub-200ms latency statistics in SQLite.
"""

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
                    spoken_text TEXT DEFAULT '',
                    final_text TEXT DEFAULT '',
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
            # Auto-migrate table if missing spoken_text / final_text columns
            cursor.execute("PRAGMA table_info(dictation_metrics);")
            columns = [col[1] for col in cursor.fetchall()]
            if "spoken_text" not in columns:
                cursor.execute("ALTER TABLE dictation_metrics ADD COLUMN spoken_text TEXT DEFAULT '';")
            if "final_text" not in columns:
                cursor.execute("ALTER TABLE dictation_metrics ADD COLUMN final_text TEXT DEFAULT '';")

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
                    date_str, spoken_text, final_text, spoken_word_count, final_word_count,
                    audio_duration_s, wpm_speed, time_saved_s, stt_latency_ms,
                    llm_latency_ms, paste_latency_ms, total_latency_ms, app_name, ai_fixes_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, spoken_text, final_text, spoken_word_count, final_word_count,
                audio_duration_s, wpm_speed, time_saved_s, stt_latency_ms,
                llm_latency_ms, paste_latency_ms, total_latency_ms, app_name, ai_fixes_count
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

    def get_recent_history(self, limit: int = 50) -> list:
        from datetime import timezone
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
                dt_str = str(r[1])
                try:
                    # Explicitly mark SQLite timestamp as UTC before converting to Local Machine Time (IST)
                    utc_dt = datetime.strptime(dt_str.split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    local_dt = utc_dt.astimezone()
                    time_str = local_dt.strftime("%I:%M %p")
                except Exception as e:
                    logger.warning(f"Failed to parse timestamp {dt_str}: {e}")
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
