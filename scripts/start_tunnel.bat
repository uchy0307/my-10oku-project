@echo off
chcp 65001 > nul
echo === cloudflared tunnel (port 7373) ===
echo Public URL will appear below (looks like https://xxxx.trycloudflare.com)
echo Copy that URL and paste it into PWA Settings -> Server URL
echo Stop with Ctrl+C
echo.
cloudflared tunnel --url http://127.0.0.1:7373
pause
