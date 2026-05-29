@echo off
chcp 65001 > nul
echo === Move cloudflared to no-space path and reconfigure service ===
echo Must be run as Administrator
echo.

set DST=C:\cloudflared
set SRC=C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.WinGet.Source_8wekyb3d8bbwe\cloudflared.exe

mkdir "%DST%" 2>nul
copy /Y "%SRC%" "%DST%\cloudflared.exe"

set CFG=C:\Windows\System32\config\systemprofile\.cloudflared\config.yml

echo Stopping any running cloudflared service
sc.exe stop cloudflared 2>nul
timeout /t 2 > nul

echo Reconfiguring service binPath (no spaces in paths so no quote nesting)
sc.exe config cloudflared binPath= "%DST%\cloudflared.exe --config %CFG% tunnel run uchy-pc"

echo.
echo Current config:
sc.exe qc cloudflared | findstr BINARY_PATH_NAME

echo.
echo Starting service
sc.exe start cloudflared

echo.
echo Status:
timeout /t 3 > nul
sc.exe query cloudflared
pause
