@echo off
chcp 65001 > nul
title gen_otona_shorts_audio
cd /d "%~dp0.."
echo === Generate otona shorts audio (edge-tts) ===
python "%~dp0gen_audio_for_scripts.py" --kind otona_shorts
echo.
echo === Done ===
rem pause (removed for no-window mode)