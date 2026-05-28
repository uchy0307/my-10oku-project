@echo off
chcp 65001 > nul
title gen_history_shorts_scripts
setlocal
cd /d "%~dp0.."
echo === Generate history shorts scripts (Gemini API) ===
python "%~dp0generate_stock_scripts.py" --kind history_shorts --count 30
echo.
echo === Done ===
rem pause (removed for no-window mode)
endlocal
