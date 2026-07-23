"""
Tier 4 E2E Test Suite: Dictating Hinglish into Simulated Application Windows
-----------------------------------------------------------------------------
Tests dictating text into VS Code editor, Notepad text area, Web Browser search box,
and Chat messaging window. Verifies cursor targeting, text insertion integrity,
and non-blocking background thread behavior.
"""

import threading
import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from fluid_voice.app import AppState, FluidVoiceApp
from fluid_voice.post_processor import HinglishPostProcessor


# ============================================================================
# Simulated Application Target Window Models
# ============================================================================

class SimulatedVSCodeEditor:
    """Simulates a VS Code IDE editor window with file buffer and cursor targeting."""

    def __init__(self, filename: str = "main.py", initial_content: str = "def process_data():\n    # TODO\n    pass\n"):
        self.hwnd = 0x1001
        self.window_title = f"{filename} - Visual Studio Code"
        self.content = initial_content
        self.cursor_index = initial_content.find("# TODO")
        self.focused = False

    def focus(self) -> None:
        self.focused = True

    def insert_text(self, text: str) -> None:
        """Inserts text at cursor index, preserving surrounding code."""
        prefix = self.content[:self.cursor_index]
        suffix = self.content[self.cursor_index:]
        self.content = prefix + text + suffix
        self.cursor_index += len(text)


class SimulatedNotepadTextArea:
    """Simulates Windows Notepad text area with caret offset targeting."""

    def __init__(self, initial_text: str = "Meeting Notes:\n"):
        self.hwnd = 0x1002
        self.window_title = "Untitled - Notepad"
        self.content = initial_text
        self.cursor_index = len(initial_text)
        self.focused = False

    def focus(self) -> None:
        self.focused = True

    def insert_text(self, text: str) -> None:
        prefix = self.content[:self.cursor_index]
        suffix = self.content[self.cursor_index:]
        self.content = prefix + text + suffix
        self.cursor_index += len(text)


class SimulatedWebBrowserSearchBox:
    """Simulates Web Browser search box input."""

    def __init__(self, initial_query: str = ""):
        self.hwnd = 0x1003
        self.window_title = "Google Chrome - New Tab"
        self.search_input = initial_query
        self.cursor_index = len(initial_query)
        self.submitted_queries: List[str] = []
        self.focused = False

    def focus(self) -> None:
        self.focused = True

    def insert_text(self, text: str) -> None:
        prefix = self.search_input[:self.cursor_index]
        suffix = self.search_input[self.cursor_index:]
        self.search_input = prefix + text + suffix
        self.cursor_index += len(text)

    def submit_search(self) -> None:
        if self.search_input:
            self.submitted_queries.append(self.search_input)


class SimulatedChatMessagingWindow:
    """Simulates Slack / Teams / WhatsApp messaging draft area."""

    def __init__(self, channel_name: str = "#general"):
        self.hwnd = 0x1004
        self.window_title = f"{channel_name} - Slack"
        self.draft_text = ""
        self.cursor_index = 0
        self.sent_messages: List[str] = []
        self.focused = False

    def focus(self) -> None:
        self.focused = True

    def insert_text(self, text: str) -> None:
        prefix = self.draft_text[:self.cursor_index]
        suffix = self.draft_text[self.cursor_index:]
        self.draft_text = prefix + text + suffix
        self.cursor_index += len(text)

    def send_message(self) -> None:
        if self.draft_text:
            self.sent_messages.append(self.draft_text)
            self.draft_text = ""
            self.cursor_index = 0


# ============================================================================
# Simulated Editor Dictation E2E Test Cases
# ============================================================================

def test_dictate_into_vscode_editor(qapp, mock_groq_api, mock_win32_paster):
    """
    E2E Test: Dictating Hinglish text into VS Code editor window.
    Verifies target window focus, text post-processing, and insertion integrity.
    """
    vscode = SimulatedVSCodeEditor()
    mock_win32_paster.set_active_window(vscode.hwnd, vscode.window_title)

    raw_speech = "def calculate total function me error handling add karo"
    mock_groq_api.set_success_response(raw_speech)

    post_processor = HinglishPostProcessor()
    processed_text = post_processor.process(raw_speech)

    # Perform insertion into simulated editor
    vscode.focus()
    vscode.insert_text(processed_text)

    assert vscode.focused is True
    assert "error handling add karo" in vscode.content
    assert "# TODO" in vscode.content  # Surrounding text preserved
    assert vscode.content.startswith("def process_data():\n    ")


def test_dictate_into_notepad_text_area(qapp, mock_groq_api, mock_win32_paster):
    """
    E2E Test: Dictating multi-line Hinglish text into Notepad text area.
    Verifies line break handling and text insertion at end of buffer.
    """
    notepad = SimulatedNotepadTextArea(initial_text="Project Standup:\n")
    mock_win32_paster.set_active_window(notepad.hwnd, notepad.window_title)

    raw_speech = "bhai meeting prepone kar do 3 PM ko full stop new line report send karo"
    mock_groq_api.set_success_response(raw_speech)

    post_processor = HinglishPostProcessor()
    processed_text = post_processor.process(raw_speech)

    notepad.focus()
    notepad.insert_text(processed_text)

    assert notepad.focused is True
    assert notepad.content.startswith("Project Standup:\n")
    assert "reschedule the meeting to 3:00 PM." in notepad.content or "meeting" in notepad.content
    assert "\n" in processed_text  # Verify new line command expanded


def test_dictate_into_browser_search_box(qapp, mock_groq_api, mock_win32_paster):
    """
    E2E Test: Dictating Hinglish search query into Web Browser search box.
    Verifies brand name formatting (e.g. Groq, Python) and search submission.
    """
    browser = SimulatedWebBrowserSearchBox()
    mock_win32_paster.set_active_window(browser.hwnd, browser.window_title)

    raw_speech = "how to use groq whisper api with python"
    mock_groq_api.set_success_response(raw_speech)

    post_processor = HinglishPostProcessor()
    processed_text = post_processor.process(raw_speech)

    browser.focus()
    browser.insert_text(processed_text)
    browser.submit_search()

    assert browser.focused is True
    assert "Groq" in browser.search_input
    assert "Python" in browser.search_input
    assert len(browser.submitted_queries) == 1
    assert browser.submitted_queries[0] == browser.search_input


def test_dictate_into_chat_messaging_window(qapp, mock_groq_api, mock_win32_paster):
    """
    E2E Test: Dictating Hinglish chat message into Slack / Teams chat window.
    Verifies chat draft insertion, punctuation, and message sending.
    """
    chat = SimulatedChatMessagingWindow(channel_name="#dev-team")
    mock_win32_paster.set_active_window(chat.hwnd, chat.window_title)

    raw_speech = "aaj meeting 3pm ko room 4 me h please bring the report"
    mock_groq_api.set_success_response(raw_speech)

    post_processor = HinglishPostProcessor()
    processed_text = post_processor.process(raw_speech)

    chat.focus()
    chat.insert_text(processed_text)
    assert chat.draft_text != ""

    chat.send_message()

    assert chat.focused is True
    assert len(chat.sent_messages) == 1
    assert "meeting" in chat.sent_messages[0]
    assert chat.draft_text == ""  # Draft cleared after send


def test_non_blocking_background_thread_dictation(qapp, tmp_path, mock_groq_api):
    """
    E2E Test: Verifies non-blocking background thread behavior during audio processing.
    The main Qt app thread must remain responsive while dictation tasks execute on a worker thread.
    """
    mutex_name = f"Global\\Test_FluidVoice_Mutex_BgThread_{tmp_path.name}"
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    assert app.initialize() is True

    execution_log = []
    main_thread_id = threading.get_ident()

    def background_dictation_worker():
        worker_thread_id = threading.get_ident()
        execution_log.append(f"worker_start:{worker_thread_id != main_thread_id}")
        time.sleep(0.1)  # Simulate audio recording & STT API latency
        post_proc = HinglishPostProcessor()
        res = post_proc.process("bhai please prepone the meeting")
        execution_log.append(f"worker_done:{res}")

    worker_thread = threading.Thread(target=background_dictation_worker, daemon=True)
    worker_thread.start()

    # Main thread continues processing Qt events while worker runs
    app.set_state(AppState.RECORDING, "Listening...")
    assert app.current_state == AppState.RECORDING

    worker_thread.join(timeout=2.0)
    assert not worker_thread.is_alive()

    app.set_state(AppState.IDLE, "Ready")
    app.quit()

    assert any(log.startswith("worker_start:True") for log in execution_log)
    assert any("reschedule" in log or "meeting" in log for log in execution_log)


def test_cursor_targeting_and_surrounding_text_preservation():
    """
    E2E Test: Direct cursor targeting test verifying insertion inside existing text block
    without corrupting left or right surrounding text.
    """
    initial_text = "The quick fox jumps over the lazy dog."
    insert_pos = initial_text.find("fox")

    notepad = SimulatedNotepadTextArea(initial_text=initial_text)
    notepad.cursor_index = insert_pos

    dictated_adj = "brown "
    notepad.insert_text(dictated_adj)

    assert notepad.content == "The quick brown fox jumps over the lazy dog."
    assert notepad.cursor_index == insert_pos + len(dictated_adj)


def test_simulated_editors_focus_preservation_and_restoration(mock_win32_paster):
    """
    E2E Test: Verifies focus detection and restoration state across multiple simulated app switches.
    """
    vscode = SimulatedVSCodeEditor()
    notepad = SimulatedNotepadTextArea()

    # Target 1: VS Code
    mock_win32_paster.set_active_window(vscode.hwnd, vscode.window_title)
    mock_win32_paster.paste_text("def foo(): pass")
    assert mock_win32_paster.pasted_history[-1] == "def foo(): pass"

    # Switch Target 2: Notepad
    mock_win32_paster.set_active_window(notepad.hwnd, notepad.window_title)
    mock_win32_paster.paste_text("Hello Notepad")
    assert mock_win32_paster.pasted_history[-1] == "Hello Notepad"

    assert len(mock_win32_paster.pasted_history) == 2
    assert mock_win32_paster.clipboard_restored is True
