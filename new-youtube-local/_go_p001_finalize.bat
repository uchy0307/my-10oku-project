@echo off
REM p001 残工程: subtitle → thumb → compile → upload
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul

REM Restore current.json to p001 first (in case it got replaced)
echo START > logs\p001_finalize_marker.txt

REM Step A: restore current.json from p001_script.json via step1
python scripts\step1_load.py > logs\p001_finalize_step1.log 2>&1

REM Step B: generate subtitle
python scripts\gen_subtitle.py > logs\p001_finalize_sub.log 2>&1

REM Step C: generate thumb
python scripts\step3b_thumbnail.py > logs\p001_finalize_thumb.log 2>&1
set RCTHUMB=%ERRORLEVEL%

REM Step D: compile night video (uses voice + clips + subtitle)
python scripts\step4_compile_night.py > logs\p001_finalize_compile.log 2>&1
set RCCOMP=%ERRORLEVEL%

REM Step E: upload to YouTube
python scripts\step5_upload.py > logs\p001_finalize_upload.log 2>&1
set RCUPL=%ERRORLEVEL%

REM Step F: verify_uploaded
python scripts\verify_uploaded.py > logs\p001_finalize_verify.log 2>&1
set RCVER=%ERRORLEVEL%

echo END thumb=%RCTHUMB% compile=%RCCOMP% upload=%RCUPL% verify=%RCVER% >> logs\p001_finalize_marker.txt
exit /b 0
