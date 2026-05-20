@echo off
REM ============================================================
REM _recover_git.bat - One-shot recovery after Cowork-side fix
REM
REM 状況：Cowork から GitHub に sanitize 済 4 commit を push し、
RPM local main を 36f01bb (origin の祖先) に巻き戻し済。
REM working tree の samurai*.bat / .py も sanitize 済に上書き済。
REM
REM auto_git_sync.bat が conflict / lock 等で失敗する場合のみ、
REM このスクリプトを double-click して手動で同期。
REM ============================================================
setlocal
cd /d "%~dp0"

echo === [1/8] disable scheduled auto_git_sync ===
schtasks /Change /TN "auto_git_sync" /DISABLE 2>nul

echo === [2/8] kill any orphan git processes ===
taskkill /F /IM git.exe 2>nul

echo === [3/8] clear stale locks ===
if exist .git\index.lock del /F /Q .git\index.lock
if exist .git\HEAD.lock  del /F /Q .git\HEAD.lock
if exist .git\refs\heads\main.lock del /F /Q .git\refs\heads\main.lock

echo === [4/8] clean leftover rebase-merge ===
if exist .git\rebase-merge      rmdir /S /Q .git\rebase-merge
if exist .git\rebase-merge.OLD_1779240155 rmdir /S /Q .git\rebase-merge.OLD_1779240155
if exist .git\REBASE_HEAD       del /F /Q .git\REBASE_HEAD
if exist .git\REBASE_HEAD.bak.1779240131 del /F /Q .git\REBASE_HEAD.bak.1779240131
if exist .git\HEAD.bak.1779240131    del /F /Q .git\HEAD.bak.1779240131
if exist .git\refs\heads\main.bak.1779240131 del /F /Q .git\refs\heads\main.bak.1779240131
if exist .git\index.bak.now     del /F /Q .git\index.bak.now
if exist .git\objects\info\commit-graphs.OLD rmdir /S /Q .git\objects\info\commit-graphs.OLD

echo === [5/8] verify HEAD points to refs/heads/main ===
echo ref: refs/heads/main> .git\HEAD

echo === [6/8] fetch origin (need network) ===
git fetch origin main
if errorlevel 1 (
  echo [recover] git fetch FAILED. Check network / PAT. Aborting before destructive ops.
  pause
  exit /b 1
)

echo === [7/8] hard-reset to origin/main (force-sync local to remote) ===
REM Working tree changes that are NOT on origin will be discarded.
REM credential-containing files in working tree are already overwritten with sanitized version.
git reset --hard origin/main
if errorlevel 1 (
  echo [recover] git reset FAILED.
  pause
  exit /b 1
)

echo === [8/8] re-enable scheduled auto_git_sync ===
schtasks /Change /TN "auto_git_sync" /ENABLE 2>nul

echo.
echo === recovery complete ===
git log --oneline -5
git status
echo.
echo Next: rotate the leaked Google OAuth credentials at:
echo   https://console.cloud.google.com/apis/credentials
echo (CLIENT_ID 898426588524-3l6tabtvvee0e1klkvcjcer4knfjl0a6 / refresh token starting 1//0e_cNze8...)
echo.
pause
