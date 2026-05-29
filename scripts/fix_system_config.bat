@echo off
chcp 65001 > nul
echo === Fixing SYSTEM config.yml credentials-file path ===
echo Must be run as Administrator
echo.

set SYS_DIR=C:\Windows\System32\config\systemprofile\.cloudflared
set TUNNEL_ID=73342c19-3388-4696-afa2-7e6418de70f3

(
echo tunnel: %TUNNEL_ID%
echo credentials-file: %SYS_DIR%\%TUNNEL_ID%.json
echo.
echo ingress:
echo   - hostname: pc.uchy0307.uk
echo     service: http://127.0.0.1:7373
echo   - service: http_status:404
) > "%SYS_DIR%\config.yml"

echo Wrote %SYS_DIR%\config.yml with correct paths
type "%SYS_DIR%\config.yml"
echo.
echo === Starting service ===
Start-Service cloudflared 2>nul
sc start cloudflared
echo.
Get-Service cloudflared
sc query cloudflared
pause
