@echo off
taskkill /F /IM python.exe /T 2>nul
echo killed > logs\_kill_done.txt
