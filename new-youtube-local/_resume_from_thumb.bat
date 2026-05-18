@echo off
REM Skip steps 0..3 (script + load + voice + clips already complete on disk).
REM Re-runs step3b_thumbnail -> step4_compile_night (patched) -> step5_upload -> verify.
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul
if not exist logs mkdir logs
echo START_resume_from_thumb > logs\resume_from_thumb_marker.txt
python run_pipeline_night.py --skip=0,1,2,3 > logs\resume_from_thumb.log 2>&1
echo END_RC_%ERRORLEVEL% >> logs\resume_from_thumb_marker.txt
