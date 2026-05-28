@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo === git add+push image style update ===
git add youtube/psych_v2/scripts/gen_stage_images.py
git add youtube/psych_v2/pipeline.mjs youtube/history_v2/pipeline.mjs youtube/shorts_v2/pipeline.mjs
git commit -m "fix: anime-style image prompts + aspect-preserve filter + no -shortest"
git push origin main
echo.
echo === DONE ===
pause
