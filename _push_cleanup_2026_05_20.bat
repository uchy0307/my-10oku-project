@echo off
REM Cleanup typo fix - remove old artefacts and push remaining .env.example fix
cd /d C:\Users\user\Documents\10oku-project
if exist .git\index.lock del /f /q .git\index.lock

REM remove the previous bat (it contains the typo string in a code comment)
if exist _push_otona_typo_fix_2026_05_20.bat git rm -f _push_otona_typo_fix_2026_05_20.bat >> _push_cleanup.log 2>&1
if exist _push_otona_typo_fix_done.txt git rm -f _push_otona_typo_fix_done.txt >> _push_cleanup.log 2>&1
if exist _push_otona_typo_fix.log git rm -f _push_otona_typo_fix.log >> _push_cleanup.log 2>&1

git add new-youtube-local\.env.example _backup_for_push\new-youtube-local__.env.example >> _push_cleanup.log 2>&1
git pull --rebase --autostash origin main >> _push_cleanup.log 2>&1
git commit -m "fix: complete channel handle rename in env.example + cleanup transient artefacts" >> _push_cleanup.log 2>&1
git push origin main >> _push_cleanup.log 2>&1
echo === push done === >> _push_cleanup.log
git log -1 --oneline >> _push_cleanup.log 2>&1
echo DONE> _push_cleanup_done.txt
