$ErrorActionPreference = 'SilentlyContinue'

Write-Output "=== 1. AppX Deployment events (last 2 hours) ==="
$evts1 = Get-WinEvent -LogName 'Microsoft-Windows-AppXDeployment/Operational' -MaxEvents 50 |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddHours(-2) } |
    Where-Object { $_.Message -match 'Claude' }
foreach ($e in $evts1) {
    Write-Output ("[" + $e.TimeCreated + "] [" + $e.LevelDisplayName + "] " + $e.Id)
    Write-Output ($e.Message.Substring(0, [Math]::Min(500, $e.Message.Length)))
    Write-Output "---"
}

Write-Output ""
Write-Output "=== 2. AppX Activation events (last 2 hours) ==="
$evts2 = Get-WinEvent -LogName 'Microsoft-Windows-TWinUI/Operational' -MaxEvents 50 |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddHours(-2) } |
    Where-Object { $_.Message -match 'Claude' }
foreach ($e in $evts2) {
    Write-Output ("[" + $e.TimeCreated + "] [" + $e.LevelDisplayName + "] " + $e.Id)
    Write-Output ($e.Message.Substring(0, [Math]::Min(500, $e.Message.Length)))
    Write-Output "---"
}

Write-Output ""
Write-Output "=== 3. Application errors (last 2 hours) ==="
$evts3 = Get-WinEvent -LogName 'Application' -MaxEvents 100 |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddHours(-2) } |
    Where-Object { $_.Message -match 'Claude' -or $_.ProviderName -match 'AppX' }
foreach ($e in $evts3) {
    Write-Output ("[" + $e.TimeCreated + "] [" + $e.LevelDisplayName + "] " + $e.ProviderName + " " + $e.Id)
    Write-Output ($e.Message.Substring(0, [Math]::Min(600, $e.Message.Length)))
    Write-Output "---"
}

Write-Output ""
Write-Output "=== 4. Windows Defender threat events (last 24h) ==="
$evts4 = Get-WinEvent -LogName 'Microsoft-Windows-Windows Defender/Operational' -MaxEvents 30 |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddHours(-24) } |
    Where-Object { $_.Message -match 'Claude' -or $_.Id -eq 1116 -or $_.Id -eq 1117 }
foreach ($e in $evts4) {
    Write-Output ("[" + $e.TimeCreated + "] [" + $e.LevelDisplayName + "] " + $e.Id)
    Write-Output ($e.Message.Substring(0, [Math]::Min(600, $e.Message.Length)))
    Write-Output "---"
}

Write-Output ""
Write-Output "=== 5. SmartScreen / SAC events (last 24h) ==="
$evts5 = Get-WinEvent -ListLog '*Application*' -EA SilentlyContinue | Where-Object { $_.LogName -match 'SmartScreen|AppLocker|CodeIntegrity' }
foreach ($l in $evts5) { Write-Output ("Log: " + $l.LogName) }
