@echo off
chcp 65001 > nul
echo === autostart setup ===
echo Creates shortcut in Startup folder so tunnel and button server auto-start at login.
echo.

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SCRIPTS=%~dp0

echo Creating shortcut: tunnel
powershell -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%STARTUP%\uchy_tunnel.lnk'); $s.TargetPath = '%SCRIPTS%start_named_tunnel.bat'; $s.WorkingDirectory = '%SCRIPTS%'; $s.WindowStyle = 7; $s.Save()"

echo Creating shortcut: button server
powershell -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%STARTUP%\uchy_button_server.lnk'); $s.TargetPath = '%SCRIPTS%start_button_server.bat'; $s.WorkingDirectory = '%SCRIPTS%'; $s.WindowStyle = 7; $s.Save()"

echo.
echo Done. Both will auto-start at next login.
echo Startup folder: %STARTUP%
pause
