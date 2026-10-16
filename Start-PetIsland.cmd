@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-island.ps1" -InstallShortcut
if errorlevel 1 pause
