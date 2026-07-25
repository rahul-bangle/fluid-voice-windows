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
