@echo off
chcp 65001 > nul
echo === Whisper setup (CPU-only torch) ===
echo Installing CPU-only torch first (avoids DLL issues)
echo.
python -m pip install --upgrade pip
python -m pip uninstall -y torch torchaudio torchvision
python -m pip install torch==2.2.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu
python -m pip install openai-whisper
echo.
echo === Setup done ===
echo Next: double-click run_whisper_psych_001.bat
pause
