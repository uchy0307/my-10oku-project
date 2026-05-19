@echo off
chcp 65001 >nul
REM Windows Task Scheduler に 「otona_youtube_night」を 21:00 JST 毎日登録
REM Local 実行: run_pipeline_night.py (Google Cloud TTS Neural2-B + Pixabay video clips)
REM [2026-05-19] VOICEVOX local 依存廃止、完全 cloud / 完全無料化軸

setlocal
set TASK_NAME=otona_youtube_night
set WORK_DIR=C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHON=python
set SCRIPT=%WORK_DIR%\run_pipeline_night.py
set LOG_FILE=%WORK_DIR%\logs\task_scheduler.log

REM 既存タスク削除（再登録）
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM 21:00 毎日実行（最大 90 分でキル）
schtasks /Create /TN "%TASK_NAME%" /SC DAILY /ST 21:00 ^
    /TR "cmd /c cd /d %WORK_DIR% && %PYTHON% %SCRIPT% >> %LOG_FILE% 2>&1" ^
    /RL HIGHEST /F

if errorlevel 1 (
    echo [register_task_night] schtasks Create FAILED
    exit /b 1
)

echo [register_task_night] OK: Task '%TASK_NAME%' registered for daily 21:00 JST
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST | findstr /B "TaskName Status"
endlocal
