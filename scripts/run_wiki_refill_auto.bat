@echo off
REM Daily auto-refill: only fetches more if stock < 500
setlocal
cd /d "%~dp0\.."
python "%~dp0wiki_image_refill.py"
