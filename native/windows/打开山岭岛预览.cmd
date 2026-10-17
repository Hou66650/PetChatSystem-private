@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Play-Meadow.ps1" -Island Camp
if errorlevel 1 pause
