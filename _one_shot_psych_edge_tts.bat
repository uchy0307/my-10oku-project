@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
REM ===================================================================
REM _one_shot_psych_edge_tts.bat  (otonaYT psych_v2 one-shot)
REM   1) youtube/psych_v2/scripts/psych_<idx>.json -> chapter text
REM   2) edge-tts ja-JP-NanamiNeural -> mp3 + srt
REM   3) youtube/psych_v2/audio/<idx>.mp3 + .srt
REM   4) git add / commit / push
REM   5) gh workflow run psych_v2.yml -f psych_index=<idx>
REM Usage:
REM   double-click  (default idx=007)
REM   _one_shot_psych_edge_tts.bat 008
REM ===================================================================

set "IDX=%~1"
if "%IDX%"=="" set "IDX=007"

cd /d "%~dp0"

set "SRC=youtube\psych_v2\scripts\psych_%IDX%.json"
set "OUT_DIR=youtube\psych_v2\audio"
set "MP3=%OUT_DIR%\%IDX%.mp3"
set "SRT=%OUT_DIR%\%IDX%.srt"
set "TXT=%TEMP%\psych_%IDX%_text.txt"
set "PS1=%TEMP%\psych_%IDX%_extract.ps1"

echo [1/6] script check: %SRC%
if not exist "%SRC%" goto :err_no_script

echo [2/6] extract chapter text to %TXT%
> "%PS1%" echo $j = Get-Content -Raw -LiteralPath '%SRC%' ^| ConvertFrom-Json
>>"%PS1%" echo $t = ($j.chapters ^| ForEach-Object { $_.text }) -join ([Environment]::NewLine + [Environment]::NewLine)
>>"%PS1%" echo [IO.File]::WriteAllText('%TXT%', $t, (New-Object Text.UTF8Encoding($false)))
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 goto :err_extract

echo [3/6] ensure edge-tts
where edge-tts >nul 2>&1
if errorlevel 1 call :install_edge
if errorlevel 1 goto :err_install

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

echo [4/6] edge-tts ja-JP-NanamiNeural - %MP3% + %SRT%
edge-tts --voice ja-JP-NanamiNeural --file "%TXT%" --write-media "%MP3%" --write-subtitles "%SRT%"
if errorlevel 1 goto :err_tts

echo [5/6] git add / commit / push
git add "%MP3%" "%SRT%"
git commit -m "audio(psych_%IDX%): edge-tts NanamiNeural one-shot"
git push

echo [6/6] gh workflow run
where gh >nul 2>&1
if errorlevel 1 (
  echo gh CLI not found - Actions tab manual run required.
) else (
  gh workflow run psych_v2.yml -f psych_index=%IDX%
)

echo.
echo === DONE ===
echo mp3: %CD%\%MP3%
echo srt: %CD%\%SRT%
pause
exit /b 0

:install_edge
python -m pip install --quiet --upgrade edge-tts==6.1.12
exit /b %errorlevel%

:err_no_script
echo NG: %SRC% not found.
goto :err

:err_extract
echo NG: chapter text extraction failed.
goto :err

:err_install
echo NG: edge-tts install failed.
goto :err

:err_tts
echo NG: edge-tts execution failed.
goto :err

:err
echo.
echo === FAILED ===
pause
exit /b 1
