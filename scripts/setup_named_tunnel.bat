@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

set HOSTNAME=pc.uchy0307.uk
set TUNNEL_NAME=uchy-pc

echo === setup named tunnel: %TUNNEL_NAME% -> %HOSTNAME% ===

echo.
echo Step 1: Create tunnel
cloudflared tunnel create %TUNNEL_NAME%
if errorlevel 1 (
    echo Tunnel may already exist. Continuing.
)

echo.
echo Step 2: Find tunnel id
for /f "tokens=1" %%a in ('cloudflared tunnel list ^| findstr /R "^[0-9a-f][0-9a-f]*-[0-9a-f]"') do (
    cloudflared tunnel list | findstr %%a | findstr %TUNNEL_NAME% >nul && set TUNNEL_ID=%%a
)

if "!TUNNEL_ID!"=="" (
    echo Could not detect tunnel id. Exiting.
    pause
    exit /b 1
)
echo Tunnel ID: !TUNNEL_ID!

echo.
echo Step 3: Write config.yml
set CONFIG=%USERPROFILE%\.cloudflared\config.yml
(
echo tunnel: !TUNNEL_ID!
echo credentials-file: %USERPROFILE%\.cloudflared\!TUNNEL_ID!.json
echo.
echo ingress:
echo   - hostname: %HOSTNAME%
echo     service: http://127.0.0.1:7373
echo   - service: http_status:404
) > "%CONFIG%"
echo wrote %CONFIG%

echo.
echo Step 4: Route DNS
cloudflared tunnel route dns %TUNNEL_NAME% %HOSTNAME%

echo.
echo === done. test with: cloudflared tunnel run %TUNNEL_NAME% ===
echo Then install service (admin powershell): cloudflared service install
pause
