@echo off
chcp 65001 > nul
echo === cloudflared install ===
echo This installs cloudflared via winget (Windows Package Manager)
echo.
winget install --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
echo.
echo === Done ===
echo Next: double-click start_tunnel.bat
pause
