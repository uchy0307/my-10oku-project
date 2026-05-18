@echo off
REM 既存 step0/1/2 成果物を流用、step3 (wikimedia clips) から再開
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PY_CMD=python"
if exist "_python_path.txt" set /p PY_CMD=<_python_path.txt
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul

if not exist "logs" mkdir logs
set "LOG=logs\resume_night_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
set "LOG=%LOG: =0%"
echo === %DATE% %TIME% start === > "%LOG%"

REM 安全のため voicevox 不要 (skip step2)。 ただし step0,1 もskip→既存 current.json + voice.wav 再利用
%PY_CMD% run_pipeline_night.py --skip=0,1,2 >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo === rc=%RC% at %DATE% %TIME% === >> "%LOG%"
echo Pipeline rc=%RC%
echo Log: %LOG%
pause
exit /b %RC%
