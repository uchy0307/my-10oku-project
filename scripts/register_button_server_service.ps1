# register_button_server_service.ps1
# Run as Administrator in PowerShell:
#   .\scripts\register_button_server_service.ps1

$ErrorActionPreference = "Stop"
$TaskName = "UchyButtonServer"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Script   = Join-Path $RepoRoot "scripts\local_button_server.py"

Write-Host "=== Button Server Task Scheduler ===" -ForegroundColor Cyan
Write-Host "Script: $Script"

# Find pythonw.exe (no console window)
$Pythonw = $null
$pw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($pw) { $Pythonw = $pw.Source }

if (-not $Pythonw) {
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py) {
        $candidate = Join-Path (Split-Path $py.Source) "pythonw.exe"
        if (Test-Path $candidate) { $Pythonw = $candidate }
    }
}

if (-not $Pythonw) {
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py) { $Pythonw = $py.Source }
}

if (-not $Pythonw) {
    Write-Host "[ERROR] Python not found in PATH" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $Pythonw"

# Remove old task
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Register task: run at logon, no window, highest privilege
$Action    = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Script`""
$Trigger   = New-ScheduledTaskTrigger -AtLogOn
$Settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host "[OK] Task registered: $TaskName" -ForegroundColor Green
Write-Host "     Auto-starts at next logon (no window)"

# Start now
Write-Host ""
Write-Host "=== Starting now ===" -ForegroundColor Cyan
Start-Process -FilePath $Pythonw -ArgumentList "`"$Script`"" -WindowStyle Hidden
Start-Sleep -Seconds 3

# Check
try {
    Invoke-WebRequest -Uri "http://localhost:7373/api" -TimeoutSec 3 -UseBasicParsing | Out-Null
    Write-Host "[OK] http://localhost:7373 is running" -ForegroundColor Green
    Write-Host "[OK] https://pc.uchy0307.uk should work now" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Server not responding yet - open https://pc.uchy0307.uk in a few seconds" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. You can close PowerShell." -ForegroundColor Green
