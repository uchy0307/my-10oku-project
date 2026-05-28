@echo off
chcp 65001 > nul
echo === inject MEMORY.md to context-injection file ===
echo Writes a fresh "rules to read" marker that future Claude sessions will see.
echo.

set INJECT_DIR=C:\Users\user\AppData\Roaming\Claude\local-agent-mode-sessions\a5e5e64e-b077-4a49-8e11-81274ae3311a\f4d2ae51-1a34-45f1-8d55-5d85622047a2\agent\memory
set MARKER=%INJECT_DIR%\_RULE_REVIEW_NEEDED.md

echo --- > "%MARKER%"
echo name: rule-review-needed >> "%MARKER%"
echo description: User pressed inject_rules button. Read MEMORY.md top 9 rules FIRST. >> "%MARKER%"
echo metadata: >> "%MARKER%"
echo   node_type: memory >> "%MARKER%"
echo   type: feedback >> "%MARKER%"
echo   priority: top >> "%MARKER%"
echo --- >> "%MARKER%"
echo. >> "%MARKER%"
echo Injected at: %date% %time% >> "%MARKER%"
echo. >> "%MARKER%"
echo うっちー様が PWA ボタンからルール再確認を要求しました。 >> "%MARKER%"
echo MEMORY.md の TOP 9 ルールをまず Read で読み直してから作業を進めること。 >> "%MARKER%"

echo Marker written: %MARKER%
echo Done.
pause
