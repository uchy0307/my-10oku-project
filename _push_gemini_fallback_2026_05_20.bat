@echo off
REM Gemini fallback hardening - commit step0_gemini.py + generate_script.mjs fixes
cd /d C:\Users\user\Documents\10oku-project
if exist .git\index.lock del /f /q .git\index.lock

git pull --rebase --autostash origin main >> _push_gemini_fallback.log 2>&1

REM Verify Python file syntax before commit
python -c "import ast; ast.parse(open(r'new-youtube-local\scripts\step0_gemini.py',encoding='utf-8').read()); print('PY-OK')" >> _push_gemini_fallback.log 2>&1
if errorlevel 1 (
  echo SYNTAX-FAIL-python >> _push_gemini_fallback.log
  echo FAIL> _push_gemini_fallback_done.txt
  exit /b 1
)

REM Verify JS file syntax
node --check youtube\scripts\generate_script.mjs >> _push_gemini_fallback.log 2>&1
if errorlevel 1 (
  echo JS-SYNTAX-FAIL >> _push_gemini_fallback.log
  echo FAIL> _push_gemini_fallback_done.txt
  exit /b 1
)

git add new-youtube-local\scripts\step0_gemini.py youtube\scripts\generate_script.mjs
git commit -m "fix(gemini): proper model fallback chain + remove dead gemma-3 models (root fix for 429 cascade)" >> _push_gemini_fallback.log 2>&1
git push origin main >> _push_gemini_fallback.log 2>&1
echo === done === >> _push_gemini_fallback.log
git log -1 --oneline >> _push_gemini_fallback.log 2>&1
echo DONE> _push_gemini_fallback_done.txt
