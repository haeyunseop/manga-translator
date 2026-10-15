@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action setup
if errorlevel 1 (echo Setup stopped. Read the error above. & pause & exit /b 1)
echo Setup finished. Double-click start-windows.bat to open MangaTrans.
pause
