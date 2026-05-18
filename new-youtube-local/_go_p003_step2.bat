@echo off
REM Resume pipeline from step2 (skip step0 gemini and step1 load, both already done for p003).
chcp 65001 >nul
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set "PY_CMD=python"
if exist "_python_path.txt" set /p PY_CMD=<_python_path.txt
if not exist "logs" mkdir logs
set TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set "TS=%TS: =0%"
set "LOG=logs\go_p003_step2_%TS%.log"
set "MARK=logs\go_p003_step2_marker.txt"
echo START_p003_step2 %DATE% %TIME% > "%MARK%"
echo === START %DATE% %TIME% === > "%LOG%"
%PY_CMD% run_pipeline_night.py --skip=0,1 >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo === END %DATE% %TIME% rc=%RC% === >> "%LOG%"
echo END_RC_%RC% %DATE% %TIME% >> "%MARK%"
echo done > logs\go_p003_step2_done.txt
