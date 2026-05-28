@echo off
chcp 65001 > nul
REM ============================================================
REM  _push_audio.bat v2
REM    Safely recover repo and push audio files only.
REM ============================================================
setlocal EnableExtensions

cd /d "%~dp0"
set BACKUP=%TEMP%\10oku_audio_backup

echo === STEP A: backup audio files to %BACKUP% ===
if exist "%BACKUP%" rmdir /s /q "%BACKUP%"
mkdir "%BACKUP%\psych" 2>nul
mkdir "%BACKUP%\history" 2>nul
copy "youtube\psych_v2\audio\*" "%BACKUP%\psych\" >nul 2>&1
copy "youtube\history_v2\audio\*" "%BACKUP%\history\" >nul 2>&1

echo Backed up:
dir /b "%BACKUP%\psych"
dir /b "%BACKUP%\history"

echo.
echo === STEP B: abort rebase, reset to origin/main ===
git rebase --abort 2>nul
git merge --abort 2>nul
git fetch origin main
git reset --hard origin/main

echo.
echo === STEP C: restore audio files ===
mkdir "youtube\psych_v2\audio" 2>nul
mkdir "youtube\history_v2\audio" 2>nul
copy "%BACKUP%\psych\*" "youtube\psych_v2\audio\" >nul 2>&1
copy "%BACKUP%\history\*" "youtube\history_v2\audio\" >nul 2>&1

echo Restored:
dir /b "youtube\psych_v2\audio"
dir /b "youtube\history_v2\audio"

echo.
echo === STEP D: also restore the python script ===
if exist "%BACKUP%\local_edge_tts_psych.py" (
  copy "%BACKUP%\local_edge_tts_psych.py" "new-youtube-local\scripts\" >nul 2>&1
)
REM local_edge_tts_psych.py: check if missing after reset
if not exist "new-youtube-local\scripts\local_edge_tts_psych.py" (
  echo [WARN] local_edge_tts_psych.py is missing. Skip its add.
)

echo.
echo === STEP E: stage, commit, push ===
git add youtube/psych_v2/audio
git add youtube/history_v2/audio
git add new-youtube-local/scripts/local_edge_tts_psych.py 2>nul

git status --short

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "feat(edge-tts): NanamiNeural mp3+srt batch (15 files)"
  if errorlevel 1 (
    echo [WARN] commit failed.
  ) else (
    git push origin main
    if errorlevel 1 (
      echo [WARN] push failed.
    ) else (
      echo [OK] push completed.
    )
  )
) else (
  echo Nothing to commit.
)

echo.
echo === DONE ===
echo Press Enter to close.
pause
endlocal
