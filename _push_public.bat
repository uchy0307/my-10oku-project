@echo off
setlocal
cd /d "%~dp0"
if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)
git fetch origin
git add -A
git commit -m "feat(youtube): default privacyStatus to public" --allow-empty
git push origin main --force
echo Done.
pause
endlocal
