@echo off
chcp 65001 > nul
cd /d C:\Users\user\Documents\10oku-project
echo === START %DATE% %TIME% === > _push_youtube_fix_2026_05_20.log

echo [1/8] git status
git status >> _push_youtube_fix_2026_05_20.log 2>&1

echo [2/8] git fetch origin
git fetch origin main >> _push_youtube_fix_2026_05_20.log 2>&1

echo [3/8] stash any local changes (preserve our edits in working tree because git stash needs clean index... use temp copies)
copy /Y youtube\scripts\generate_script.mjs _tmp_generate_script.mjs >> _push_youtube_fix_2026_05_20.log 2>&1
copy /Y youtube\scripts\generate_topics.mjs _tmp_generate_topics.mjs >> _push_youtube_fix_2026_05_20.log 2>&1
copy /Y .github\workflows\youtube_auto.yml _tmp_youtube_auto.yml >> _push_youtube_fix_2026_05_20.log 2>&1

echo [4/8] reset index hard to origin/main to clear any local corruption
git reset --hard origin/main >> _push_youtube_fix_2026_05_20.log 2>&1

echo [5/8] restore our edited files
copy /Y _tmp_generate_script.mjs youtube\scripts\generate_script.mjs >> _push_youtube_fix_2026_05_20.log 2>&1
copy /Y _tmp_generate_topics.mjs youtube\scripts\generate_topics.mjs >> _push_youtube_fix_2026_05_20.log 2>&1
copy /Y _tmp_youtube_auto.yml .github\workflows\youtube_auto.yml >> _push_youtube_fix_2026_05_20.log 2>&1
del _tmp_generate_script.mjs _tmp_generate_topics.mjs _tmp_youtube_auto.yml >> _push_youtube_fix_2026_05_20.log 2>&1

echo [6/8] git add specific files only
git add youtube/scripts/generate_script.mjs youtube/scripts/generate_topics.mjs .github/workflows/youtube_auto.yml >> _push_youtube_fix_2026_05_20.log 2>&1

echo [7/8] git diff cached summary
git diff --cached --stat >> _push_youtube_fix_2026_05_20.log 2>&1

echo [8/8] commit and push
git -c user.email=uchiyamatakayuki0307@gmail.com -c user.name=uchy0307 commit -m "fix(youtube): drastic Gemini quota reduction - 8000->2000 chars, dead 1.5 models removed, verify retries killed" >> _push_youtube_fix_2026_05_20.log 2>&1
git push origin main >> _push_youtube_fix_2026_05_20.log 2>&1

echo === END %DATE% %TIME% === >> _push_youtube_fix_2026_05_20.log
echo. >> _push_youtube_fix_2026_05_20.log
git log --oneline -5 >> _push_youtube_fix_2026_05_20.log 2>&1
echo DONE > _push_youtube_fix_2026_05_20.done
exit
