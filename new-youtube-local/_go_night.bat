@echo off
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul
echo START_v2 > logs\go_marker.txt
python run_pipeline_night.py --skip=0,2 > logs\go_log.txt 2>&1
echo END_RC_%ERRORLEVEL% >> logs\go_marker.txt
