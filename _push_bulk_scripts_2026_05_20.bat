@echo off
chcp 65001 > nul
cd /d C:\Users\user\Documents\10oku-project
echo === START %DATE% %TIME% === > _push_bulk_scripts_2026_05_20.log

echo [1/9] git status (may show corrupt index)
git status >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [2/9] git fetch origin main
git fetch origin main >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [3/9] snapshot edited files to _tmp
mkdir _tmp_bulk 2> nul
copy /Y youtube\topics.json _tmp_bulk\topics.json >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y youtube\scripts\generate_script.mjs _tmp_bulk\generate_script.mjs >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y youtube\scripts\bulk_generate_scripts.mjs _tmp_bulk\bulk_generate_scripts.mjs >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y .github\workflows\bulk_generate_scripts.yml _tmp_bulk\bulk_generate_scripts.yml >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y youtube\inputs\scripts\README.md _tmp_bulk\README.md >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [4/9] reset --hard origin/main to clear corrupt index
git reset --hard origin/main >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [5/9] restore edited files
copy /Y _tmp_bulk\topics.json youtube\topics.json >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y _tmp_bulk\generate_script.mjs youtube\scripts\generate_script.mjs >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y _tmp_bulk\bulk_generate_scripts.mjs youtube\scripts\bulk_generate_scripts.mjs >> _push_bulk_scripts_2026_05_20.log 2>&1
copy /Y _tmp_bulk\bulk_generate_scripts.yml .github\workflows\bulk_generate_scripts.yml >> _push_bulk_scripts_2026_05_20.log 2>&1
mkdir youtube\inputs\scripts 2> nul
copy /Y _tmp_bulk\README.md youtube\inputs\scripts\README.md >> _push_bulk_scripts_2026_05_20.log 2>&1
rmdir /S /Q _tmp_bulk

echo [6/9] git add specific files
git add youtube/topics.json youtube/scripts/generate_script.mjs youtube/scripts/bulk_generate_scripts.mjs .github/workflows/bulk_generate_scripts.yml youtube/inputs/scripts/README.md >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [7/9] diff cached summary
git diff --cached --stat >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [8/9] commit
git commit -m "feat(youtube): pre-stock infra - bulk generator + JSON consumer fast path + 20 new topics" >> _push_bulk_scripts_2026_05_20.log 2>&1

echo [9/9] push
git push origin main >> _push_bulk_scripts_2026_05_20.log 2>&1

echo === END %DATE% %TIME% === >> _push_bulk_scripts_2026_05_20.log
echo === pushed. log: _push_bulk_scripts_2026_05_20.log ===
type _push_bulk_scripts_2026_05_20.log | findstr /R "^\[\|error\|FAIL\|fatal\|main ->"
