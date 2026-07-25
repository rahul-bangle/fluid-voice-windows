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
