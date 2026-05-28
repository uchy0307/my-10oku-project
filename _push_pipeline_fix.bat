@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo === git push (pipeline.mjs duration fix) ===
git push origin main
echo.
echo === retrigger psych_v2 ===
where gh >nul 2>&1
if errorlevel 1 (
  echo gh CLI not found. Manually trigger psych_v2.yml from GitHub Actions tab.
) else (
  gh workflow run psych_v2.yml -f psych_index=001
)
echo.
echo === DONE ===
pause
