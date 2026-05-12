@echo off
setlocal
cd /d "%~dp0"
if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)
git add -A
git commit -m "feat: self-heal + note draft-edit + YouTube full impl (per Gemini spec)"
git push origin main
echo Done.
pause
endlocal
