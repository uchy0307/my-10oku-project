@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo === note-auto/upload-attachments.mjs ===
echo cwd=%CD%
echo.
node note-auto\upload-attachments.mjs %*
set EC=%ERRORLEVEL%
echo.
echo Exit code: %EC%
if not "%EC%"=="0" (
  echo ERROR - press any key to close
  pause >nul
) else (
  echo OK - closing in 10 sec...
  timeout /t 10 >nul
)
endlocal
