@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-NativeService.ps1"
if errorlevel 1 goto failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Play-Meadow.ps1" -Island Home
if errorlevel 1 goto failed
exit /b 0
:failed
echo Pait Island could not start. Keep the error above for diagnosis.
pause
exit /b 1
