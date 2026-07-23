"""
tests/unit/test_context_engine.py
----------------------------------
Unit test suite for ContextEngine (fluid_voice.context_engine).
Tier 1: Feature Coverage, Classification Accuracy & Prompt Formatting (Happy Path)
Tier 2: Boundary, Win32 Edge Cases, Elevated Admin Processes, Lock Screen & Recovery
"""

import sys
import time
from unittest.mock import MagicMock, patch
import pytest

from fluid_voice.context_engine import (
    AppCategory,
    AppContext,
    WindowContextDetector,
    AppClassifier,
    ContextEngine,
)
from fluid_voice.post_processor import HinglishPostProcessor


class MockAccessDenied(Exception):
    """Mock exception class matching psutil.AccessDenied behavior."""
    def __init__(self, pid=None):
        self.pid = pid


class MockNoSuchProcess(Exception):
    """Mock exception class matching psutil.NoSuchProcess behavior."""
    def __init__(self, pid=None):
        self.pid = pid


def create_mock_psutil(exe_name="slack.exe", side_effect=None):
    """Creates a mock psutil module structure for dependency-independent unit testing."""
    mock_ps = MagicMock()
    mock_ps.AccessDenied = MockAccessDenied
    mock_ps.NoSuchProcess = MockNoSuchProcess
    if side_effect:
        mock_ps.Process.side_effect = side_effect
    else:
        proc = MagicMock()
        proc.name.return_value = exe_name
        mock_ps.Process.return_value = proc
    return mock_ps


# ============================================================================
# Tier 1: Core Functionality, Data Model & Classification Accuracy Tests
# ============================================================================

def test_app_category_enum_and_app_context_dataclass():
    """Tier 1: Verifies AppCategory enum values, AppContext properties, and to_dict method."""
    ctx = AppContext(
        app_category=AppCategory.CODE,
        exe_name="code.exe",
        window_title="context_engine.py - Visual Studio Code",
        hwnd=0x1234,
        pid=5678,
        browser_domain=None,
    )

    assert ctx.app_category == AppCategory.CODE
    assert ctx.category == "CODE"
    assert ctx.app_name == "code.exe"
    assert ctx.domain is None

    d = ctx.to_dict()
    assert d["app_name"] == "code.exe"
    assert d["exe_name"] == "code.exe"
    assert d["category"] == "CODE"
    assert d["app_category"] == "CODE"
    assert d["hwnd"] == 0x1234
    assert d["pid"] == 5678
    assert d["window_title"] == "context_engine.py - Visual Studio Code"


def test_app_classifier_native_apps():
    """Tier 1: Tests direct executable classification for CODE, MESSAGING, FORMAL, and GENERAL apps."""
    classifier = AppClassifier()

    assert classifier.classify("code.exe", "") == AppCategory.CODE
    assert classifier.classify("cursor.exe", "") == AppCategory.CODE
    assert classifier.classify("slack.exe", "") == AppCategory.MESSAGING
    assert classifier.classify("teams.exe", "") == AppCategory.MESSAGING
    assert classifier.classify("winword.exe", "") == AppCategory.FORMAL
    assert classifier.classify("excel.exe", "") == AppCategory.FORMAL
    assert classifier.classify("spotify.exe", "") == AppCategory.GENERAL


def test_app_classifier_browser_domains():
    """Tier 1: Tests domain extraction and category classification for browser titles."""
    classifier = AppClassifier()

    # YouTube -> GENERAL, YouTube
    cat, dom = classifier.classify_context("chrome.exe", "Lofi Hip Hop Radio - YouTube - Google Chrome")
    assert cat == AppCategory.GENERAL
    assert dom == "YouTube"

    # GitHub -> CODE, GitHub
    cat, dom = classifier.classify_context("msedge.exe", "fluid_voice_windows/context_engine.py at main · GitHub - Microsoft Edge")
    assert cat == AppCategory.CODE
    assert dom == "GitHub"

    # GitLab -> CODE, GitLab
    cat, dom = classifier.classify_context("firefox.exe", "Project Overview · GitLab")
    assert cat == AppCategory.CODE
    assert dom == "GitLab"

    # Gmail -> FORMAL, Gmail
    cat, dom = classifier.classify_context("chrome.exe", "Inbox (12) - user@gmail.com - Google Chrome")
    assert cat == AppCategory.FORMAL
    assert dom == "Gmail"

    # Slack Web -> MESSAGING, Slack
    cat, dom = classifier.classify_context("brave.exe", "Slack | #general | Workspace")
    assert cat == AppCategory.MESSAGING
    assert dom == "Slack"


def test_get_active_context_native_messaging_app():
    """Tier 1: Verifies active window detection for native Slack app via psutil."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil("slack.exe")

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x10001), \
         patch("win32gui.GetWindowText", return_value="Slack | General Channel"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(100, 4001)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "slack.exe"
        assert ctx.app_name == "slack.exe"
        assert ctx.window_title == "Slack | General Channel"
        assert ctx.category == "MESSAGING"
        assert ctx.app_category == AppCategory.MESSAGING
        assert ctx.domain is None


def test_get_current_context_native_code_app():
    """Tier 1: Verifies get_current_context for VS Code."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil("code.exe")

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x10002), \
         patch("win32gui.GetWindowText", return_value="context_engine.py - Visual Studio Code"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(101, 4002)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_current_context()
        assert ctx.exe_name == "code.exe"
        assert ctx.category == "CODE"
        assert ctx.app_category == AppCategory.CODE
        assert ctx.domain is None


def test_get_active_context_native_win32_query_process_fallback():
    """Tier 1: Verifies process executable resolution using native Win32 QueryFullProcessImageNameW API."""
    engine = ContextEngine()

    mock_kernel32 = MagicMock()
    mock_kernel32.OpenProcess.return_value = 0x9999

    def fake_query_full_image_name(hProcess, flags, buf, size_ref):
        buf.value = r"C:\Program Files\Microsoft VS Code\code.exe"
        return 1

    mock_kernel32.QueryFullProcessImageNameW.side_effect = fake_query_full_image_name

    with patch("fluid_voice.context_engine.HAS_PSUTIL", False), \
         patch("fluid_voice.context_engine.psutil", None), \
         patch("win32gui.GetForegroundWindow", return_value=0x10002), \
         patch("win32gui.GetWindowText", return_value="context_engine.py - Visual Studio Code"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(101, 4002)), \
         patch("ctypes.windll.kernel32", mock_kernel32), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "code.exe"
        assert ctx.category == "CODE"


def test_build_llm_context_prompt_formatting():
    """Tier 1: Verifies build_llm_context_prompt generates appropriate system prompt hints."""
    engine = ContextEngine()

    msg_ctx = AppContext(app_category=AppCategory.MESSAGING, browser_domain="Slack")
    msg_prompt = engine.build_llm_context_prompt(msg_ctx)
    assert "MESSAGING" in msg_prompt
    assert "Slack" in msg_prompt

    code_ctx = AppContext(app_category=AppCategory.CODE)
    code_prompt = engine.build_llm_context_prompt(code_ctx)
    assert "CODE" in code_prompt
    assert "snake_case" in code_prompt or "IDE" in code_prompt

    formal_ctx = AppContext(app_category=AppCategory.FORMAL)
    formal_prompt = engine.build_llm_context_prompt(formal_ctx)
    assert "FORMAL" in formal_prompt
    assert "punctuation" in formal_prompt or "Word" in formal_prompt

    gen_ctx = AppContext(app_category=AppCategory.GENERAL)
    gen_prompt = engine.build_llm_context_prompt(gen_ctx)
    assert "GENERAL" in gen_prompt


# ============================================================================
# Tier 2: Boundary, Win32 Edge Cases, Elevated Admin Processes & Recovery
# ============================================================================

def test_edge_case_null_foreground_window_handle():
    """Tier 2: Verifies hwnd=0 returns Unknown default context without throwing exceptions."""
    engine = ContextEngine()

    with patch("win32gui.GetForegroundWindow", return_value=0), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.app_name == "Unknown"
        assert ctx.window_title == ""
        assert ctx.category == "GENERAL"
        assert ctx.domain is None


def test_edge_case_lock_screen_active():
    """Tier 2: Verifies workstation lock screen returns LockApp.exe fallback context."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil("LockApp.exe")

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x99999), \
         patch("win32gui.GetWindowText", return_value="LockApp"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(99, 9999)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "lockapp.exe"
        assert ctx.app_category == AppCategory.GENERAL
        assert ctx.domain is None


def test_edge_case_elevated_admin_process_access_denied():
    """Tier 2: Verifies Elevated admin process (AccessDenied exception) returns ElevatedProcess fallback."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil(side_effect=MockAccessDenied(pid=8888))

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x88888), \
         patch("win32gui.GetWindowText", return_value="Administrator: Windows PowerShell"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(88, 8888)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "ElevatedProcess"
        assert ctx.app_name == "ElevatedProcess"
        assert ctx.window_title == "Administrator: Windows PowerShell"
        assert ctx.category == "GENERAL"


def test_edge_case_empty_window_title():
    """Tier 2: Verifies window with empty title bar still classifies category via executable name."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil("code.exe")

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x77777), \
         patch("win32gui.GetWindowText", return_value=""), \
         patch("win32process.GetWindowThreadProcessId", return_value=(77, 7777)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "code.exe"
        assert ctx.window_title == ""
        assert ctx.category == "CODE"
        assert ctx.domain is None


def test_edge_case_rapid_focus_switch_invalid_hwnd():
    """Tier 2: Verifies Win32 exception (invalid window handle mid-call) is caught cleanly."""
    engine = ContextEngine()

    with patch("win32gui.GetForegroundWindow", return_value=0x66666), \
         patch("win32gui.GetWindowText", side_effect=RuntimeError("Win32 error: Invalid window handle")), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.app_name == "Unknown"
        assert ctx.category == "GENERAL"


def test_edge_case_browser_new_tab_or_local_file():
    """Tier 2: Verifies browser blank tabs or local file URLs return domain=None."""
    engine = ContextEngine()
    mock_ps = create_mock_psutil("chrome.exe")

    with patch.dict("sys.modules", {"psutil": mock_ps}), \
         patch("fluid_voice.context_engine.HAS_PSUTIL", True), \
         patch("fluid_voice.context_engine.psutil", mock_ps), \
         patch("win32gui.GetForegroundWindow", return_value=0x55555), \
         patch("win32gui.GetWindowText", return_value="New Tab - Google Chrome"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(55, 5555)), \
         patch("sys.platform", "win32"), \
         patch("fluid_voice.context_engine.HAS_WIN32", True):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "chrome.exe"
        assert ctx.domain is None
        assert ctx.category == "GENERAL"


def test_edge_case_non_windows_platform_fallback():
    """Tier 2: Verifies non-Windows environment gracefully returns UnsupportedOS context."""
    engine = ContextEngine()

    with patch("fluid_voice.context_engine.HAS_WIN32", False), \
         patch("fluid_voice.context_engine.win32gui", None):

        ctx = engine.get_active_context()
        assert ctx.exe_name == "UnsupportedOS"
        assert ctx.category == "GENERAL"
        assert ctx.domain is None


def test_post_processor_integration_with_context():
    """Verifies HinglishPostProcessor.process_with_groq_llm accepts context and passes hint to LLM."""
    post_proc = HinglishPostProcessor()
    ctx = AppContext(app_category=AppCategory.CODE, exe_name="code.exe")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "def foo(): pass"}}]
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = post_proc.process_with_groq_llm(
            raw_text="def foo pass",
            api_key="test-api-key",
            context=ctx
        )

        assert mock_post.called
        call_args = mock_post.call_args[1]
        json_payload = call_args["json"]
        system_content = json_payload["messages"][0]["content"]

        assert "Context:" in system_content
        assert "CODE" in system_content
        assert result == "Def foo(): pass." or "def foo(): pass" in result.lower()


# ============================================================================
# Tier 2 Edge Cases: Browser Domain Parsing Refinements
# ============================================================================

def test_edge_case_stack_overflow_domain_rule():
    """Verifies 'stack overflow' (with space) correctly maps to Stack Overflow domain and CODE category."""
    classifier = AppClassifier()
    cat, dom = classifier.classify_context("opera.exe", "Stack Overflow - How to parse string in Python? - Opera")
    assert cat == AppCategory.CODE
    assert dom == "Stack Overflow"

    cat2, dom2 = classifier.classify_context("msedge.exe", "Stack Overflow - Where Developers Learn, Share, & Build Careers - Microsoft Edge")
    assert cat2 == AppCategory.CODE
    assert dom2 == "Stack Overflow"


def test_edge_case_browser_delimiter_em_dash_and_en_dash():
    """Verifies _extract_generic_browser_domain splits titles on em-dash (' — ') and en-dash (' – ')."""
    classifier = AppClassifier()

    cat, dom = classifier.classify_context("firefox.exe", "Wikipedia, the free encyclopedia — Mozilla Firefox")
    assert cat == AppCategory.GENERAL
    assert dom == "Wikipedia, the free encyclopedia"

    cat2, dom2 = classifier.classify_context("firefox.exe", "Python Documentation – Mozilla Firefox")
    assert cat2 == AppCategory.GENERAL
    assert dom2 == "Python Documentation"


def test_edge_case_internal_browser_pages_ignored():
    """Verifies blank/internal browser start pages return domain=None and GENERAL category."""
    classifier = AppClassifier()

    internal_titles = [
        "Speed Dial - Opera",
        "Start Page - Vivaldi",
        "Microsoft Edge Workspace - Personal",
        "Mozilla Firefox",
        "about:blank",
        "chrome://settings",
        "edge://flags",
        "opera://extensions",
    ]

    for title in internal_titles:
        cat, dom = classifier.classify_context("chrome.exe", title)
        assert cat == AppCategory.GENERAL, f"Expected GENERAL for title '{title}', got {cat}"
        assert dom is None, f"Expected domain None for title '{title}', got '{dom}'"


def test_edge_case_vs_code_web_precedence_over_github():
    """Verifies 'vs code' rule takes precedence over 'github' in DOMAIN_RULES for web IDE titles."""
    classifier = AppClassifier()
    cat, dom = classifier.classify_context("brave.exe", "vs code web - github.dev - Brave")
    assert cat == AppCategory.CODE
    assert dom == "VS Code"

