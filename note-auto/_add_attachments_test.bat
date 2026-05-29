@echo off
chcp 65001 > nul
title add_attachments_test
cd /d "%~dp0.."
echo === ADD ATTACHMENTS DRY RUN (first 5) ===
node note-auto\add-attachments-only.mjs --max=5 --dry-run
echo.
echo If above looks right, run real with: node note-auto\add-attachments-only.mjs --max=5
pause
