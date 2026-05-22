@echo off
REM ============================================================
REM  Register Windows Task Scheduler entry:
REM    "10oku_edge_tts_history_poll" — every hour (xx:25)
REM
REM  Runs:
REM    python new-youtube-local\scripts\local_edge_tts_history_poll.py
REM
REM  Idempotent: deletes existing task first.
REM ============================================================
setlocal

set TASK_NAME=10oku_edge_tts_history_poll
set REPO=%~dp0..
set SCRIPT=%REPO%\new-youtube-local\scripts\local_edge_tts_history_poll.py

REM Locate python
for /f "delims=" %%P in ('where python 2^>nul') do (
  set PYEXE=%%P
  goto :found
)
echo [ERROR] python not on PATH. Install Python 3.11+ and re-run.
exit /b 2

:found
echo Using python: %PYEXE%
echo Script: %SCRIPT%

REM Delete existing task (ignore error)
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM Create new task: every 60 min, repeat every 1h indefinitely, run whether logged-in or not
schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "\"%PYEXE%\" \"%SCRIPT%\"" ^
  /SC HOURLY ^
  /MO 1 ^
  /ST 00:25 ^
  /RL LIMITED ^
  /F

if errorlevel 1 (
  echo [ERROR] schtasks create failed.
  exit /b 1
)

echo.
echo Task registered: %TASK_NAME%
echo Run now to test:  schtasks /Run /TN "%TASK_NAME%"
echo Inspect log:      type "%REPO%\new-youtube-local\logs\local_edge_tts_history_poll.log"
endlocal
