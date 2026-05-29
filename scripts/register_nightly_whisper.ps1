# register_nightly_whisper.ps1
# 夜23時に whisper SRT を一括生成するタスク登録
# Run as Administrator

$ErrorActionPreference = "Stop"
$TaskName = "UchyNightlyWhisper"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Script   = Join-Path $RepoRoot "scripts\nightly_whisper.py"

$Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Host "[ERROR] python.exe not found" -ForegroundColor Red
    exit 1
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action    = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`""
$Trigger   = New-ScheduledTaskTrigger -Daily -At "23:00"
$Settings  = New-ScheduledTaskSettingsSet `
              -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
              -RestartCount 2 `
              -RestartInterval (New-TimeSpan -Minutes 30) `
              -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType S4U

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host "[OK] Task registered: $TaskName (daily at 23:00 JST)" -ForegroundColor Green
