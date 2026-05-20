@echo off
REM Fix typo otona_no_psychology -> otona_psychology, commit only the 4 files
cd /d C:\Users\user\Documents\10oku-project

REM remove stale lock if present
if exist .git\index.lock del /f /q .git\index.lock

REM pull rebase first (autostash to keep working tree changes)
git pull --rebase --autostash origin main >> _push_otona_typo_fix.log 2>&1

REM stage ONLY the 4 typo-fix files
git add daily_report_2026-05-19.md daily_report_2026-05-20.md new-youtube-local\scripts\step0_gemini.py new-youtube-local\scripts\step5_upload.py

REM commit (allow empty just in case)
git commit -m "fix: rename otona_no_psychology -> otona_psychology (channel handle typo fix)" >> _push_otona_typo_fix.log 2>&1

REM push
git push origin main >> _push_otona_typo_fix.log 2>&1

echo === push done === >> _push_otona_typo_fix.log
git log -1 --oneline >> _push_otona_typo_fix.log 2>&1
echo DONE> _push_otona_typo_fix_done.txt
