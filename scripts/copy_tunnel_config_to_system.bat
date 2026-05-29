@echo off
chcp 65001 > nul
echo === copy tunnel config to SYSTEM profile ===
echo Service runs as SYSTEM user, needs config at different path.
echo (Must be run as Administrator)
echo.
set SRC=%USERPROFILE%\.cloudflared
set DST=C:\Windows\System32\config\systemprofile\.cloudflared
echo SRC: %SRC%
echo DST: %DST%
mkdir "%DST%" 2>nul
xcopy /Y /E "%SRC%\*" "%DST%\"
echo.
echo === Restarting cloudflared service ===
net stop cloudflared
net start cloudflared
echo Done. Wait 30s and try the URL again.
pause
