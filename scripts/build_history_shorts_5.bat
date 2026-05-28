@echo off
chcp 65001 > nul
title build_history_shorts_5
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0.."
echo === Build history shorts 5 videos ===

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)

set DONE=0
for %%I in (001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018 019 020 021 022 023 024 025 026 027 028 029 030 031 032 033 034 035 036 037 038 039 040 041 042 043 044 045 046 047 048 049 050) do (
  if !DONE! lss 5 (
    if exist "youtube\shorts_v2\audio\%%I.mp3" (
      if not exist "youtube\shorts_v2\.work\%%I\output.mp4" (
        echo --- building shorts %%I ---
        set SHORT_INDEX=%%I
        node youtube\shorts_v2\pipeline.mjs
        if !errorlevel! equ 99 (
          echo [SKIP] shorts %%I already uploaded
        ) else if !errorlevel! neq 0 (
          echo [WARN] shorts %%I failed errorlevel=!errorlevel!
        ) else (
          set /a DONE+=1
          echo [OK] shorts %%I done. total=!DONE!
        )
      ) else (
        echo [SKIP] %%I already built
      )
    ) else (
      echo [SKIP] %%I audio missing
    )
  )
)

echo.
echo === Finished: !DONE! / 5 ===
rem pause (removed for no-window mode)
endlocal
