@echo off
setlocal
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)

echo [1/4] git pull --rebase origin main (sync remote first)
git pull --rebase origin main

echo [2/4] git add -A
git add -A

echo [3/4] git commit (may say "nothing to commit" if already committed)
git commit -m "feat: self-heal + note draft-edit + YouTube full impl (per Gemini spec)"

echo [4/4] git push origin main
git push origin main

echo.
echo === Done ===
pause
endlocal
