"""
fluid_voice.context_engine
--------------------------
Dynamic Active App & Browser Tab Context Engine for FluidVoice V2.
Detects foreground Win32 active window, process name, category, and browser tab domain
for LLM context injection.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import sys
import time
from typing import Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Safe Win32 Imports
try:
    import win32gui
    import win32process
    import win32api
    import ctypes
    HAS_WIN32 = True
except ImportError:
    win32gui = None
    win32process = None
    win32api = None
    ctypes = None
    HAS_WIN32 = False

# Safe Psutil Imports
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


class AppCategory(str, Enum):
    """Active application categories for context-aware dictation formatting."""
    MESSAGING = "MESSAGING"
    CODE = "CODE"
    FORMAL = "FORMAL"
    GENERAL = "GENERAL"


@dataclass
class AppContext:
    """Dataclass holding details of the active foreground application and browser tab context."""
    app_category: AppCategory = AppCategory.GENERAL
    exe_name: str = ""
    window_title: str = ""
    hwnd: int = 0
    pid: int = 0
    browser_domain: Optional[str] = None
    browser_url: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def category(self) -> str:
        """Alias for category string (e.g. 'CODE', 'MESSAGING')."""
        return self.app_category.value if isinstance(self.app_category, AppCategory) else str(self.app_category)

    @property
    def app_name(self) -> str:
        """Alias for application executable name or fallback name."""
        return self.exe_name or "Unknown"

    @property
    def domain(self) -> Optional[str]:
        """Alias for browser domain."""
        return self.browser_domain

    def to_dict(self) -> dict:
        """Converts AppContext instance to dictionary."""
        return {
            "app_name": self.app_name,
            "exe_name": self.exe_name,
            "window_title": self.window_title,
            "category": self.category,
            "app_category": self.category,
            "hwnd": self.hwnd,
            "pid": self.pid,
            "domain": self.domain,
            "browser_domain": self.browser_domain,
            "browser_url": self.browser_url,
            "timestamp": self.timestamp,
        }


class WindowContextDetector:
    """
    Detects current foreground active window using Win32 APIs or psutil fallback.
    Maintains a pid -> exe_name cache for sub-millisecond execution latency.
    """

    def __init__(self):
        self._pid_cache: Dict[int, str] = {}

    def get_foreground_window_info(self) -> Tuple[int, str, int]:
        """
        Returns (hwnd, window_title, pid) for the currently focused foreground window.
        Returns (0, "", 0) if no window is focused or Win32 is unavailable or raises an exception.
        """
        if not HAS_WIN32 or sys.platform != "win32" or not win32gui:
            return 0, "", 0

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or hwnd == 0:
                return 0, "", 0

            title = win32gui.GetWindowText(hwnd) if hasattr(win32gui, "GetWindowText") else ""
            title_clean = title.strip() if title else ""
            
            pid = 0
            if win32process and hasattr(win32process, "GetWindowThreadProcessId"):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)

            return hwnd, title_clean, pid
        except Exception as e:
            logger.warning(f"Error getting foreground window info: {e}")
            return 0, "", 0

    def get_process_exe_name(self, pid: int) -> str:
        """
        Resolves process executable name for a given PID.
        Uses cached result, psutil, or Win32 QueryFullProcessImageNameW fallback.
        Returns executable name (e.g. 'code.exe').
        """
        if not pid or pid <= 0:
            return ""

        if pid in self._pid_cache:
            return self._pid_cache[pid]

        exe_name = ""
        access_denied = False

        # Method A: psutil
        if HAS_PSUTIL and psutil:
            try:
                proc = psutil.Process(pid)
                name = proc.name()
                if name:
                    exe_name = os.path.basename(name).lower()
            except (psutil.AccessDenied, AttributeError):
                access_denied = True
            except Exception as e:
                logger.debug(f"psutil process resolution failed for PID {pid}: {e}")

        # Method B: Native Win32 QueryFullProcessImageNameW fallback
        if not exe_name and HAS_WIN32 and ctypes and hasattr(ctypes, "windll"):
            try:
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                kernel32 = getattr(ctypes.windll, "kernel32", None)
                if kernel32 and hasattr(kernel32, "OpenProcess"):
                    hProcess = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if hProcess:
                        try:
                            buf = ctypes.create_unicode_buffer(1024)
                            size = ctypes.c_ulong(1024)
                            if hasattr(kernel32, "QueryFullProcessImageNameW") and kernel32.QueryFullProcessImageNameW(hProcess, 0, buf, ctypes.byref(size)):
                                exe_name = os.path.basename(buf.value).lower()
                        finally:
                            kernel32.CloseHandle(hProcess)
            except Exception as e:
                logger.debug(f"Win32 QueryFullProcessImageNameW failed for PID {pid}: {e}")

        if not exe_name and access_denied:
            exe_name = "ElevatedProcess"

        if exe_name:
            self._pid_cache[pid] = exe_name

        return exe_name

    def detect_active_window(self) -> Tuple[int, str, int, str]:
        """
        Combines window detection and process resolution.
        Returns (hwnd, window_title, pid, exe_name).
        """
        hwnd, title, pid = self.get_foreground_window_info()
        exe_name = self.get_process_exe_name(pid)
        return hwnd, title, pid, exe_name


class AppClassifier:
    """
    Classifies active application into AppCategory based on process executable name,
    window title keywords, and web application domain rules.
    """

    CODE_EXES: Set[str] = {
        "code.exe", "cursor.exe", "pycharm.exe", "pycharm64.exe",
        "idea.exe", "idea64.exe", "windowsterminal.exe", "wt.exe",
        "powershell.exe", "pwsh.exe", "cmd.exe", "sublime_text.exe",
        "clion64.exe", "webstorm64.exe", "rider64.exe", "notepad++.exe",
        "devenv.exe", "bash.exe", "wsl.exe"
    }

    MESSAGING_EXES: Set[str] = {
        "slack.exe", "teams.exe", "ms-teams.exe", "discord.exe",
        "whatsapp.exe", "telegram.exe", "signal.exe", "element.exe",
        "messenger.exe"
    }

    FORMAL_EXES: Set[str] = {
        "winword.exe", "outlook.exe", "notion.exe", "excel.exe",
        "powerpnt.exe", "onenote.exe", "acrobat.exe", "acrord32.exe",
        "foxitreader.exe", "wordpad.exe"
    }

    BROWSER_EXES: Set[str] = {
        "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
        "opera.exe", "vivaldi.exe", "arc.exe"
    }

    # Structure: (keyword_in_title_lower, domain_name, AppCategory)
    DOMAIN_RULES = [
        ("youtube", "YouTube", AppCategory.GENERAL),
        ("vs code", "VS Code", AppCategory.CODE),
        ("github", "GitHub", AppCategory.CODE),
        ("gitlab", "GitLab", AppCategory.CODE),
        ("stack overflow", "Stack Overflow", AppCategory.CODE),
        ("stackoverflow", "Stack Overflow", AppCategory.CODE),
        ("replit", "Replit", AppCategory.CODE),
        ("jupyter", "Jupyter", AppCategory.CODE),
        ("gmail", "Gmail", AppCategory.FORMAL),
        ("google docs", "Google Docs", AppCategory.FORMAL),
        ("google sheets", "Google Sheets", AppCategory.FORMAL),
        ("google slides", "Google Slides", AppCategory.FORMAL),
        ("overleaf", "Overleaf", AppCategory.FORMAL),
        ("confluence", "Confluence", AppCategory.FORMAL),
        ("linear", "Linear", AppCategory.FORMAL),
        ("notion", "Notion", AppCategory.FORMAL),
        ("outlook", "Outlook", AppCategory.FORMAL),
        ("linkedin", "LinkedIn", AppCategory.FORMAL),
        ("slack", "Slack", AppCategory.MESSAGING),
        ("discord", "Discord", AppCategory.MESSAGING),
        ("whatsapp", "WhatsApp", AppCategory.MESSAGING),
        ("telegram", "Telegram", AppCategory.MESSAGING),
        ("messenger", "Messenger", AppCategory.MESSAGING),
        ("reddit", "Reddit", AppCategory.GENERAL),
        ("chatgpt", "ChatGPT", AppCategory.GENERAL),
        ("claude", "Claude", AppCategory.GENERAL),
    ]

    MESSAGING_TITLE_PATTERNS: Tuple[str, ...] = (
        "slack", "teams", "discord", "whatsapp", "telegram", "messenger"
    )

    FORMAL_TITLE_PATTERNS: Tuple[str, ...] = (
        "google docs", "google sheets", "google slides", "notion",
        "microsoft word", "overleaf", "confluence", "linear", "gmail", "outlook", "linkedin"
    )

    CODE_TITLE_PATTERNS: Tuple[str, ...] = (
        "github", "gitlab", "stack overflow", "replit", "jupyter", "vs code"
    )

    def classify_context(self, exe_name: str, window_title: str) -> Tuple[AppCategory, Optional[str]]:
        """
        Classifies active application context into (AppCategory, browser_domain).
        """
        exe_lower = (exe_name or "").lower().strip()
        title_lower = (window_title or "").lower().strip()

        # Check Browser Execution Path
        if exe_lower in self.BROWSER_EXES:
            if not title_lower:
                return AppCategory.GENERAL, None

            # Ignore blank / internal browser start pages
            internal_prefixes = (
                "new tab",
                "speed dial",
                "start page",
                "microsoft edge workspace",
                "mozilla firefox",
                "about:blank",
                "chrome://",
                "edge://",
                "opera://",
                "file://",
            )
            if any(title_lower.startswith(prefix) for prefix in internal_prefixes) or any(
                proto in title_lower for proto in ("about:blank", "chrome://", "edge://", "opera://", "file://")
            ):
                return AppCategory.GENERAL, None

            for kw, domain_name, cat in self.DOMAIN_RULES:
                if kw in title_lower:
                    return cat, domain_name

            extracted_domain = self._extract_generic_browser_domain(window_title)
            return AppCategory.GENERAL, extracted_domain

        # Direct Executable Match for Native Desktop Apps
        if exe_lower in self.CODE_EXES:
            return AppCategory.CODE, None
        if exe_lower in self.MESSAGING_EXES:
            return AppCategory.MESSAGING, None
        if exe_lower in self.FORMAL_EXES:
            return AppCategory.FORMAL, None

        # Title Pattern Fallback for Unclassified Apps / Web Apps
        for pattern in self.MESSAGING_TITLE_PATTERNS:
            if pattern in title_lower:
                return AppCategory.MESSAGING, None

        for pattern in self.FORMAL_TITLE_PATTERNS:
            if pattern in title_lower:
                return AppCategory.FORMAL, None

        for pattern in self.CODE_TITLE_PATTERNS:
            if pattern in title_lower:
                return AppCategory.CODE, None

        return AppCategory.GENERAL, None

    def classify(self, exe_name: str, window_title: str) -> AppCategory:
        """
        Classifies active application into an AppCategory enum value.
        """
        cat, _ = self.classify_context(exe_name, window_title)
        return cat

    def _extract_generic_browser_domain(self, title: str) -> Optional[str]:
        """Extracts page title string prior to browser suffix delimiters."""
        if not title:
            return None
        for sep in [" - ", " · ", " | ", " — ", " – "]:
            if sep in title:
                parts = title.split(sep)
                if len(parts) > 1:
                    return parts[0].strip()
        return title if len(title) < 50 else title[:50].strip()


class ContextEngine:
    """
    Main Context Engine orchestrator for FluidVoice V2.
    Integrates WindowContextDetector and AppClassifier to produce AppContext.
    """

    def __init__(self, detector: Optional[WindowContextDetector] = None, classifier: Optional[AppClassifier] = None):
        self.detector = detector or WindowContextDetector()
        self.classifier = classifier or AppClassifier()

    def get_current_context(self) -> AppContext:
        """
        Samples foreground active window and classifies active app category.
        Returns populated AppContext.
        """
        if not HAS_WIN32 or sys.platform != "win32":
            return AppContext(
                app_category=AppCategory.GENERAL,
                exe_name="UnsupportedOS",
                window_title="",
                hwnd=0,
                pid=0,
                browser_domain=None,
                timestamp=time.time()
            )

        hwnd, title, pid, exe_name = self.detector.detect_active_window()

        if not hwnd or hwnd == 0:
            return AppContext(
                app_category=AppCategory.GENERAL,
                exe_name=exe_name or "Unknown",
                window_title=title or "",
                hwnd=0,
                pid=pid,
                browser_domain=None,
                timestamp=time.time()
            )

        category, domain = self.classifier.classify_context(exe_name, title)
        return AppContext(
            app_category=category,
            exe_name=exe_name,
            window_title=title,
            hwnd=hwnd,
            pid=pid,
            browser_domain=domain,
            timestamp=time.time()
        )

    def get_active_context(self) -> AppContext:
        """Alias for get_current_context() to satisfy interface contract."""
        return self.get_current_context()

    def build_llm_context_prompt(self, context: AppContext) -> str:
        """
        Generates Stage 2 LLM prompt hint based on active AppContext.
        """
        cat = context.app_category
        cat_val = cat.value if isinstance(cat, AppCategory) else str(cat)

        domain_str = f" ({context.domain})" if context.domain else ""

        if cat_val == AppCategory.MESSAGING.value:
            return f"Target app: MESSAGING{domain_str} (Slack/Teams). Format dictation for instant messaging: keep casual tone, allow common abbreviations and emoticons if spoken, avoid stiff formal document formatting."
        elif cat_val == AppCategory.CODE.value:
            return f"Target app: CODE{domain_str} (IDE/Terminal). Format dictation for software development: strictly preserve code symbols, variable names (snake_case/camelCase), function names, technical jargon, and CLI commands without unwanted prose punctuation."
        elif cat_val == AppCategory.FORMAL.value:
            return f"Target app: FORMAL{domain_str} (Word/Notion/Docs). Format dictation for professional writing: apply full formal punctuation, proper sentence capitalization, structured paragraphs, and polished vocabulary."
        else:
            return f"Target app: GENERAL{domain_str}. Apply standard Hinglish post-processing rules with balanced punctuation and formatting."
