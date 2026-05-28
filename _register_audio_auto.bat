@echo off
chcp 65001 > nul
REM ============================================================
REM  _register_audio_auto.bat (simple version)
REM    Register Task Scheduler entry to run audio gen daily.
REM    Right-click -> Run as administrator for best results.
REM ============================================================
setlocal

set TASK=ClaudeAudioAuto
set REPO=%~dp0
set TARGET=%REPO%_regenerate_all_audio.bat

echo === Registering: %TASK% ===
echo Target: %TARGET%
echo Time:   Daily 03:00

schtasks /Delete /TN "%TASK%" /F >nul 2>&1

schtasks /Create /TN "%TASK%" /TR "\"%TARGET%\"" /SC DAILY /ST 03:00 /RL LIMITED /F

if errorlevel 1 (
  echo.
  echo [ERROR] Task registration failed. Try Run as administrator.
  pause
  exit /b 1
)

echo.
echo === DONE ===
echo Task "%TASK%" registered. Runs daily at 03:00.
echo To stop: schtasks /Delete /TN "%TASK%" /F
pause
endlocal
