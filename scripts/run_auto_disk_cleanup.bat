@echo off
chcp 65001 > nul
title auto_disk_cleanup
cd /d C:\Users\user\Documents\10oku-project
echo === Auto Disk Cleanup ===
python scripts\auto_disk_cleanup.py
echo === Done ===
