@echo off
chcp 65001 > nul
title cleanup_images
cd /d C:\Users\user\Documents\10oku-project
echo === Image Cleanup (auto execute) ===
echo dry-run preview:
python scripts\cleanup_images.py --dry-run
echo.
echo === DELETE ===
python scripts\cleanup_images.py
echo.
echo === Done ===