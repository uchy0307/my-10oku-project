@echo off
REM ===========================================================================
REM Initial bulk download of 1000+ Wikimedia Commons images for stock library.
REM Logs to scripts/wiki_refill.log
REM ===========================================================================
setlocal
cd /d "%~dp0\.."
echo === wiki image refill (initial, target 1000) ===
python "%~dp0wiki_image_refill.py" --initial
echo === finished ===
