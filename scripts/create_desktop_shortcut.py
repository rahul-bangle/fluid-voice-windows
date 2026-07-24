"""
scripts/create_desktop_shortcut.py
----------------------------------
Creates a 1-click Windows Desktop Shortcut VeloVoice.lnk on the user's Desktop.
"""

import os
import sys
from pathlib import Path


def create_shortcut():
    desktop_dir = Path(os.path.expanduser("~/Desktop"))
    project_dir = Path(__file__).resolve().parent.parent
    vbs_path = project_dir / "VeloVoice.vbs"
    shortcut_path = desktop_dir / "VeloVoice.lnk"

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = "wscript.exe"
        shortcut.Arguments = f'"{vbs_path}"'
        shortcut.WorkingDirectory = str(project_dir)
        shortcut.Description = "VeloVoice - Low Latency Voice OS"
        shortcut.Save()
        print(f"✅ Created Desktop Shortcut: {shortcut_path}")
        return True
    except Exception as e:
        print(f"Failed to create shortcut via win32com: {e}")
        # Fallback via PowerShell
        ps_cmd = (
            f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut_path}"); '
            f'$s.TargetPath = "wscript.exe"; '
            f'$s.Arguments = "`"{vbs_path}`""; '
            f'$s.WorkingDirectory = "`"{project_dir}`""; '
            f'$s.Description = "VeloVoice - Low Latency Voice OS"; '
            f'$s.Save()'
        )
        ret = os.system(f'powershell -Command "{ps_cmd}"')
        if ret == 0:
            print(f"✅ Created Desktop Shortcut via PowerShell: {shortcut_path}")
            return True
        return False


if __name__ == "__main__":
    create_shortcut()
