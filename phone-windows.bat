@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0scripts\windows.ps1" goto not_extracted
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action phone
set "MANGATRANS_LAUNCH_EXIT=%ERRORLEVEL%"
if not "%MANGATRANS_LAUNCH_EXIT%"=="0" goto failed
pause
exit /b 0

:not_extracted
echo MangaTrans must be fully extracted before running this file.
echo Close the ZIP preview, extract ALL files, then run this file from the extracted folder.
echo The scripts folder must be next to this file.
pause
exit /b 1

:failed
echo MangaTrans phone stopped with an error. Read the message above.
pause
exit /b 1
