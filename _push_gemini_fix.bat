@echo off
setlocal
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set.
  pause
  exit /b 1
)

git add youtube/scripts/generate_script.mjs
git commit -m "fix(gemini): use gemini-2.0-flash (1.5-pro-latest is deprecated)"
git push origin main

echo.
echo Done. Re-run YouTube Auto Cycle workflow on GitHub.
pause
endlocal
