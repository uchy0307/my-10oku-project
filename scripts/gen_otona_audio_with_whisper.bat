@echo off
chcp 65001 > nul
title gen_otona_audio_with_whisper
cd /d "%~dp0.."

echo === STEP 1: edge-tts audio (psych) ===
python "%~dp0gen_audio_for_scripts.py" --kind psych
if errorlevel 1 (
  echo [WARN] audio generation had errors
)

echo.
echo === STEP 2: whisper word-level timing (psych audio dir) ===
python "%~dp0whisper_subtitle_gen.py" --dir youtube\psych_v2\audio
if errorlevel 1 (
  echo [WARN] whisper failed - pipeline will fall back to ASS even-distribution
)

echo.
echo === STEP 3: refine SRT (original script text + whisper timing) ===
python "%~dp0refine_srt.py" --kind psych --all
if errorlevel 1 (
  echo [WARN] refine_srt failed
)

echo.
echo === Done: audio + accurate SRT ready ===
rem pause (removed for no-window mode)