@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-NativeService.ps1"
if errorlevel 1 (
  echo 账号服务未能启动，请查看上方提示。
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Play-Meadow.ps1"
