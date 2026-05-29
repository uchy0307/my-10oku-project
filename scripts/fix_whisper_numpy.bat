@echo off
chcp 65001 > nul
echo === Fix Whisper numpy compat ===
python -m pip install "numpy<2"
echo.
echo === Done ===
echo Next: double-click run_whisper_psych_001.bat
pause
