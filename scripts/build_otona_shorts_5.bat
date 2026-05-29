@echo off
chcp 65001 > nul
title build_otona_shorts_5
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0.."
echo === Build otona shorts (C-pattern: cut from psych long) ===

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)

if "%OTONA_YOUTUBE_REFRESH_TOKEN%"=="" (
  echo [FATAL] OTONA_YOUTUBE_REFRESH_TOKEN is not set.
  echo This would upload to the history channel by mistake.
  echo Set OTONA_YOUTUBE_REFRESH_TOKEN in .env first.
  exit /b 2
)

rem ----- step 1: for each psych long with output.mp4 + srt, generate intro/peak/outro shorts -----
set MADE=0
for %%I in (001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018 019 020 021 022 023 024 025 026 027 028 029 030 031 032 033 034 035 036 037 038 039 040 041 042 043 044 045 046 047 048 049 050) do (
  if exist "youtube\psych_v2\.work\%%I\output.mp4" (
    if exist "youtube\psych_v2\audio\%%I.srt" (
      echo --- make shorts from psych %%I ---
      python scripts\make_shorts_from_long.py --kind psych --index %%I
      if !errorlevel! equ 0 (
        set /a MADE+=1
      ) else (
        echo [WARN] make_shorts failed for %%I rc=!errorlevel!
      )
    )
  )
)
echo.
echo === Shorts generated from %MADE% long videos ===

rem ----- step 2: upload up to 5 unposted shorts (otona channel) -----
echo --- upload psych shorts (max 5) ---
node scripts\upload_shorts.mjs --kind psych --count 5

echo.
echo === build_otona_shorts_5 DONE ===
endlocal
