@echo off
chcp 65001 > nul
title build_otona_3
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0.."
echo === Build otona (psych) 3 videos ===

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)

set DONE=0
for %%I in (001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018 019 020 021 022 023 024 025 026 027 028 029 030 031 032 033 034 035 036 037 038 039 040 041 042 043 044 045 046 047 048 049 050) do (
  if !DONE! lss 3 (
    if exist "youtube\psych_v2\audio\%%I.mp3" (
      if not exist "youtube\psych_v2\.work\%%I\output.mp4" (
        echo --- building psych %%I ---
        set PSYCH_INDEX=%%I
        node youtube\psych_v2\pipeline.mjs
        if !errorlevel! equ 99 (
          echo [SKIP] psych %%I already uploaded
        ) else if !errorlevel! neq 0 (
          echo [WARN] psych %%I failed errorlevel=!errorlevel!
        ) else (
          set /a DONE+=1
          echo [OK] psych %%I done. total=!DONE!
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
echo === Finished: !DONE! / 3 ===
rem pause (removed for no-window mode)
endlocal
