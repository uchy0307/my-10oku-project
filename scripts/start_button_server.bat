@echo off
chcp 65001 > nul
echo === local button server ===
echo Listening on http://localhost:7373
echo Stop with Ctrl+C
cd /d "%~dp0\.."
python scripts\local_button_server.py
pause
