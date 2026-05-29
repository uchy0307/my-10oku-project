@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0\.."
echo === 1/3 history full ===
python scripts\assemble_video.py --kind history --audio youtube\history_v2\audio\007.mp3 --out C:\Users\user\Documents\10oku_samples\30min_01_history_akechi.mp4 --duration 1180
echo.
echo === 2/3 psych full ===
python scripts\assemble_video.py --kind psych --audio youtube\psych_v2\.work\001\narration.mp3 --out C:\Users\user\Documents\10oku_samples\30min_02_psych.mp4 --duration 1630
echo.
echo === 3/3 shorts (history-based) ===
python scripts\assemble_video.py --kind shorts --audio youtube\history_v2\audio\007.mp3 --out C:\Users\user\Documents\10oku_samples\30min_03_shorts_history.mp4 --duration 60
echo.
echo === DONE ===
echo output: C:\Users\user\Documents\10oku_samples\
pause
