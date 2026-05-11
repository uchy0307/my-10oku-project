@echo off
setlocal

cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
  echo ERROR: GITHUB_TOKEN environment variable is not set.
  echo Set it in PowerShell first:
  echo   $env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
  pause
  exit /b 1
)

echo [1/7] git init
git init

echo [2/7] git add -A
git add -A
git add -f HANDOFF.md note-auto/ .github/workflows/note_auto_post.yml handoff-bundle/ 2>nul

echo [3/7] git commit
git commit -m "feat: 10oku-project initial setup with HANDOFF + note B-plan auto-post"

echo [4/7] git branch -M main
git branch -M main

echo [5/7] git remote add origin
git remote remove origin 2>nul
git remote add origin https://uchy0307:%GITHUB_TOKEN%@github.com/uchy0307/my-10oku-project.git

echo [6/7] git push -u origin main --force
git push -u origin main --force

echo [7/7] last 5 commits:
git log --oneline -5

echo.
echo ==========================================
echo SUCCESS: GitHub push completed.
echo.
echo Next:
echo  1) Open https://github.com/uchy0307/my-10oku-project/actions
echo  2) Run "YouTube Auto Cycle" / "note Auto Post" workflows
echo  3) After tests pass, PC OFF is OK.
echo.
echo Secrets needed:
echo   - NOTE_EMAIL / NOTE_PASSWORD (for note auto-post)
echo   - GEMINI_API_KEY / ELEVENLABS_* / YOUTUBE_* (already set)
echo ==========================================

pause
endlocal
exit /b 0
