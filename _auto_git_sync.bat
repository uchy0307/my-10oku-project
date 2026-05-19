@echo off
cd /d C:\Users\user\Documents\10oku-project
git pull --rebase --autostash origin main
git add -A
git commit -m "auto: dispatch sync"
git push origin main
echo.
echo === done ===
timeout /t 5
