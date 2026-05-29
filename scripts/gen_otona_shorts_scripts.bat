@echo off
chcp 65001 > nul
title gen_otona_shorts_scripts
setlocal
cd /d "%~dp0.."
echo === Generate otona shorts scripts (Gemini API) ===
python "%~dp0generate_stock_scripts.py" --kind otona_shorts --count 30
echo.
echo === Done ===
rem pause (removed for no-window mode)
endlocal
