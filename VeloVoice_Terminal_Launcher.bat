@echo off
title VeloVoice - Live Terminal Logs
cd /d "C:\Users\rahul\teamwork_projects\fluid_voice_windows"
cls
echo ================================================================================
echo VELOVOICE WINDOWS - LIVE TERMINAL LOGS AND DICTATION DAEMON
echo ================================================================================
echo Date: July 24, 2026
echo Workspace: C:\Users\rahul\teamwork_projects\fluid_voice_windows
echo Hotkey: Alt+S
echo Secondary Hotkeys: Ctrl+Alt+C, Alt+Shift+J, ESC
echo ================================================================================
echo.
python -m fluid_voice
echo.
echo Application exited with code %errorlevel%.
pause
