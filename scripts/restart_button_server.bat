@echo off
chcp 65001 >nul
echo === restart button server (windowless) ===
echo Finding process on port 7373
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":7373"') do (
    if not "%%a"=="0" (
        echo Killing PID %%a
        taskkill /F /PID %%a 2>nul
    )
)
timeout /t 2 /nobreak >nul
echo Starting new server with pythonw (no window)
cd /d %~dp0\..
start "" "C:\Users\user\AppData\Local\Programs\Python\Python312\pythonw.exe" scripts\local_button_server.py
echo Done. No console window will appear.
timeout /t 3 /nobreak >nul
exit
