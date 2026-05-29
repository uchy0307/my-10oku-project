@echo off
chcp 65001 > nul
title cleanup_images_preview
cd /d C:\Users\user\Documents\10oku-project
echo === Image Cleanup Preview (dry-run only) ===
python scripts\cleanup_images.py --dry-run
echo.
echo === Preview Done (no files deleted) ===
