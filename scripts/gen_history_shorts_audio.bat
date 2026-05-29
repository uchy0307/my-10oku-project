@echo off
chcp 65001 > nul
title gen_history_shorts_audio
cd /d "%~dp0.."
echo === Generate history shorts audio (edge-tts) ===
python "%~dp0gen_audio_for_scripts.py" --kind history_shorts
echo.
echo === Done ===
rem pause (removed for no-window mode)