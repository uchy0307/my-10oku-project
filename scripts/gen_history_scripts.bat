@echo off
chcp 65001 > nul
title gen_history_scripts
setlocal
cd /d "%~dp0.."
echo === Generate history scripts (Gemini API) ===
echo Loading .env...
python "%~dp0generate_stock_scripts.py" --kind history --count 30
echo.
echo === Done ===
rem pause (removed for no-window mode)
endlocal
