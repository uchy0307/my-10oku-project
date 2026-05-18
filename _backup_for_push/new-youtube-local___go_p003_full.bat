@echo off
REM Full pipeline run for p003 (state.json already marks p001/p002 processed).
REM Step0 will pick p003 ("触れたい欲求の正体"). Requires VOICEVOX engine on localhost:50021.
chcp 65001 >nul
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set "PY_CMD=python"
if exist "_python_path.txt" set /p PY_CMD=<_python_path.txt
if not exist "logs" mkdir logs
set TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set "TS=%TS: =0%"
set "LOG=logs\go_p003_%TS%.log"
set "MARK=logs\go_p003_marker.txt"
echo START_p003 %DATE% %TIME% > "%MARK%"
echo === START %DATE% %TIME% === > "%LOG%"
%PY_CMD% run_pipeline_night.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo === END %DATE% %TIME% rc=%RC% === >> "%LOG%"
echo END_RC_%RC% %DATE% %TIME% >> "%MARK%"
echo log=%LOG% rc=%RC% > logs\go_p003_done.txt
