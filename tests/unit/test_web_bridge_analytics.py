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
    assert "avg_total_ms" in data
