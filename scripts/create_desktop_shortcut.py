"""
scripts/create_desktop_shortcut.py
----------------------------------
Creates a 1-click Windows Desktop Shortcut VeloVoice.lnk on the user's Desktop.
"""

import os
import sys
from pathlib import Path


def create_shortcut():
    user_home = Path(os.path.expanduser("~"))
    desktop_dirs = [user_home / "OneDrive" / "Desktop", user_home / "Desktop"]
    project_dir = Path(__file__).resolve().parent.parent
    bat_path = project_dir / "VeloVoice_Terminal_Launcher.bat"

    created = False
    for d in desktop_dirs:
        if d.exists():
            shortcut_path = d / "VeloVoice.lnk"
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.TargetPath = str(bat_path)
                shortcut.WorkingDirectory = str(project_dir)
                shortcut.Description = "VeloVoice Terminal Launcher"
                shortcut.Save()
                print(f"✅ Created Terminal Desktop Shortcut: {shortcut_path}")
                created = True
            except Exception as e:
                print(f"Failed to create shortcut at {shortcut_path}: {e}")
    return created


if __name__ == "__main__":
    create_shortcut()
