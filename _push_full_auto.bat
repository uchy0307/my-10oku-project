@echo off
setlocal
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)

echo [1/4] git fetch
git fetch origin

echo [2/4] git add -A
git add -A

echo [3/4] git commit
git commit -m "feat(note): full auto sync-drafts + 200 v3 articles" --allow-empty

echo [4/4] git push origin main --force
git push origin main --force

echo.
echo === Done ===
echo Next:
echo  1) Actions tab on GitHub
echo  2) Run "note Auto Post" workflow once manually
echo  3) Cron will run twice daily afterward
pause
endlocal
