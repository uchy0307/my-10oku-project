@echo off
chcp 65001 > nul
echo === Register button server to startup folder ===
echo.

set BAT_PATH=%~dp0start_button_server.bat
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set LNK=%STARTUP%\UchyButtonServer.lnk

REM Create shortcut via PowerShell
powershell -NoProfile -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%LNK%'); $s.TargetPath = '%BAT_PATH%'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()"

if exist "%LNK%" (
    echo OK: shortcut created at %LNK%
) else (
    echo FAILED to create shortcut
    pause
    exit /b 1
)

echo.
echo === Starting now (one-time) ===
start "" "%BAT_PATH%"

echo.
echo Done. From next logon, button server auto-starts via startup folder.
pause
