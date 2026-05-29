# register_daily_cycle.ps1
# Daily cycle を Windows タスクスケジューラに登録
# Run as Administrator:
#   .\scripts\register_daily_cycle.ps1

$ErrorActionPreference = "Stop"
$TaskName = "UchyDailyCycle"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Script   = Join-Path $RepoRoot "scripts\daily_cycle.py"

Write-Host "=== Daily Cycle Task Registration ===" -ForegroundColor Cyan
Write-Host "Script: $Script"

# Use console python (visible logs would write to file), but pythonw for silent
$Python = $null
$py = Get-Command python.exe -ErrorAction SilentlyContinue
if ($py) { $Python = $py.Source }
if (-not $Python) {
    Write-Host "[ERROR] python.exe not found" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $Python"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 毎日 08:00 JST に起動。長時間実行OK (max 6h)
$Action    = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`""
$Trigger   = New-ScheduledTaskTrigger -Daily -At "08:00"
$Settings  = New-ScheduledTaskSettingsSet `
              -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
              -RestartCount 2 `
              -RestartInterval (New-TimeSpan -Minutes 30) `
              -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType S4U

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host "[OK] Task registered: $TaskName (daily at 08:00 JST)" -ForegroundColor Green
Write-Host "      Will auto-start if PC was off at trigger time (StartWhenAvailable)"

Write-Host ""
Write-Host "=== Test run (manual trigger) ===" -ForegroundColor Cyan
Write-Host "To test immediately:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Or run directly:"
Write-Host "  python `"$Script`""
