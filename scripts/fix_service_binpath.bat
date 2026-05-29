@echo off
chcp 65001 > nul
echo === Fix cloudflared service binPath with --config arg ===
echo Must be run as Administrator
echo.

sc.exe config cloudflared binPath= "\"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.WinGet.Source_8wekyb3d8bbwe\cloudflared.exe\" --config \"C:\Windows\System32\config\systemprofile\.cloudflared\config.yml\" tunnel run uchy-pc"

echo.
echo === Current service config ===
sc.exe qc cloudflared

echo.
echo === Starting service ===
sc.exe start cloudflared

echo.
echo === Status ===
sc.exe query cloudflared
pause
