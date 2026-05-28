@echo off
chcp 65001 > nul
REM ============================================================
REM  _regenerate_all_audio.bat (FINAL - commit-per-file)
REM    Re-generate all psych_v2 and history_v2 mp3+srt locally.
REM    Commit + push after EACH file so nothing can be lost.
REM ============================================================
setlocal EnableExtensions

set REPO=%~dp0
set PYTHONIOENCODING=utf-8
cd /d "%REPO%"

echo.
echo === STEP 1: ensure python and edge-tts ===
where python >nul 2>&1
if errorlevel 1 (
  echo [FATAL] python not on PATH.
  pause
  exit /b 2
)

python -c "import edge_tts" >nul 2>&1
if errorlevel 1 (
  echo Installing edge-tts...
  python -m pip install --upgrade edge-tts
  if errorlevel 1 (
    echo [FATAL] pip install failed.
    pause
    exit /b 3
  )
)

echo.
echo === STEP 2: ensure on main, sync remote ===
git rebase --abort 2>nul
git merge --abort 2>nul
git checkout main 2>nul
git fetch origin main 2>nul
git reset --hard origin/main

if not exist "youtube\psych_v2\audio" mkdir "youtube\psych_v2\audio"
if not exist "youtube\history_v2\audio" mkdir "youtube\history_v2\audio"

echo.
echo === STEP 3: psych_v2 (001-006) - commit per file ===
for %%I in (001 002 003 004 005 006) do (
  if exist "%REPO%youtube\psych_v2\audio\%%I.mp3" (
    echo [SKIP] psych %%I exists.
  ) else (
    if exist "%REPO%youtube\psych_v2\scripts\psych_%%I.json" (
      echo --- generating psych %%I ---
      python "%REPO%new-youtube-local\scripts\local_edge_tts_psych.py" %%I
      if errorlevel 1 (
        echo [WARN] psych %%I generation failed.
      ) else (
        git add "youtube/psych_v2/audio/%%I.mp3" "youtube/psych_v2/audio/%%I.srt" 2>nul
        git commit -m "audio(psych_%%I): edge-tts NanamiNeural"
        git push origin main
        echo [OK] psych %%I committed and pushed.
      )
    ) else (
      echo [SKIP] psych_%%I.json not present.
    )
  )
)

echo.
echo === STEP 4: history_v2 (001-009) - commit per file ===
for %%I in (001 002 003 004 005 006 007 008 009) do (
  if exist "%REPO%youtube\history_v2\audio\%%I.mp3" (
    echo [SKIP] history %%I exists.
  ) else (
    if exist "%REPO%youtube\history_v2\scripts\long_%%I.json" (
      echo --- generating history %%I ---
      python "%REPO%new-youtube-local\scripts\local_edge_tts_history.py" %%I
      if errorlevel 1 (
        echo [WARN] history %%I generation failed.
      ) else (
        git add "youtube/history_v2/audio/%%I.mp3" "youtube/history_v2/audio/%%I.srt" 2>nul
        git commit -m "audio(history_%%I): edge-tts NanamiNeural"
        git push origin main
        echo [OK] history %%I committed and pushed.
      )
    ) else (
      echo [SKIP] long_%%I.json not present.
    )
  )
)

echo.
echo === DONE ===
echo psych audio:
dir /b "%REPO%youtube\psych_v2\audio\*.mp3" 2>nul
echo history audio:
dir /b "%REPO%youtube\history_v2\audio\*.mp3" 2>nul
echo.
pause
endlocal
