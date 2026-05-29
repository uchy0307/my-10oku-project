# register_inbox_responder_service.ps1
# inbox_auto_responder.py をタスクスケジューラに登録（5分ごと実行）
# Run as Administrator:
#   .\scripts\register_inbox_responder_service.ps1

$ErrorActionPreference = "Stop"
$TaskName = "UchyInboxAutoResponder"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Script   = Join-Path $RepoRoot "scripts\inbox_auto_responder.py"

Write-Host "=== Inbox Auto-Responder Task Registration ===" -ForegroundColor Cyan
Write-Host "Script: $Script"

$Pythonw = $null
$pw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($pw) { $Pythonw = $pw.Source }
if (-not $Pythonw) {
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py) {
        $candidate = Join-Path (Split-Path $py.Source) "pythonw.exe"
        if (Test-Path $candidate) { $Pythonw = $candidate } else { $Pythonw = $py.Source }
    }
}
if (-not $Pythonw) {
    Write-Host "[ERROR] Python not found" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $Pythonw"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Trigger: every 5 minutes from now, indefinitely
$Action    = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Script`" --once"
$Trigger   = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::FromDays(3650))
$Settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -RestartCount 2
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host "[OK] Task registered: $TaskName (runs every 5 min)" -ForegroundColor Green

# Test run
Write-Host ""
Write-Host "=== Test run ===" -ForegroundColor Cyan
& $Pythonw $Script --once

Write-Host ""
Write-Host "Done. From now on, every smartphone message will get an auto-reply within 5 min." -ForegroundColor Green
