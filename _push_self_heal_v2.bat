@echo off
setlocal
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)

echo [1/4] git fetch origin
git fetch origin

echo [2/4] git add -A
git add -A

echo [3/4] git commit
git commit -m "feat: self-heal + note draft-edit + YouTube full impl (per Gemini spec)" --allow-empty

echo [4/4] git push origin main --force (overwrite remote)
git push origin main --force

echo.
echo === Done ===
pause
endlocal
