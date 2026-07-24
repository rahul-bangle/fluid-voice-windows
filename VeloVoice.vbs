' VeloVoice Silent Windows Launcher
' Launches VeloVoice in background without opening black CMD / PowerShell windows.

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get current directory of this script
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Run pythonw -m fluid_voice in background (window style 0 = hidden)
WshShell.CurrentDirectory = scriptPath
WshShell.Run "pythonw -m fluid_voice", 0, False
