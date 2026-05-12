@echo off
setlocal
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN not set
  pause
  exit /b 1
)

echo [1/3] git add -A
git add -A

echo [2/3] git commit (may say nothing to commit if already done)
git commit -m "feat: self-heal + note draft-edit + YouTube full impl (per Gemini spec)" --allow-empty

echo [3/3] git push origin main --force-with-lease (overwrite remote with our state)
git push origin main --force-with-lease

echo.
echo === Done ===
pause
endlocal
