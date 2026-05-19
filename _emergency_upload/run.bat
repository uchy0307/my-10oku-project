@echo off
chcp 65001 > nul
cd /d C:\Users\user\Documents\10oku-project\_emergency_upload
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set TS=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TS=%TS: =0%

echo === START %DATE% %TIME% === > run2.log

where python >> run2.log 2>&1
where ffmpeg >> run2.log 2>&1

echo --- Running build_and_upload.py --- >> run2.log
python build_and_upload.py >> run2.log 2>&1
set RC=%ERRORLEVEL%

echo === END %DATE% %TIME% rc=%RC% === >> run2.log
echo %RC% > run2.done
exit
