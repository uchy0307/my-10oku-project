@echo off
chcp 65001 >nul
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
REM Load .env vars (simple parse)
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if not "%%A"=="" if not "%%A:~0,1%"=="#" set %%A=%%B
)
python scripts\step2_voice_voicevox.py > _step2_standalone_stdout.txt 2> _step2_standalone_stderr.txt
set RC=%ERRORLEVEL%
echo rc=%RC% > _step2_standalone_done.txt
