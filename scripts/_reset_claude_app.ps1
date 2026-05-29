$ErrorActionPreference = 'Stop'
Write-Output "=== Step 1: Stop CoworkVMService to break loop ==="
try {
    Stop-Service -Name CoworkVMService -Force
    Set-Service -Name CoworkVMService -StartupType Manual
    Write-Output "Service stopped + StartupType=Manual"
} catch {
    Write-Output ("Stop service failed: " + $_.Exception.Message)
}

Write-Output ""
Write-Output "=== Step 2: Reset-AppxPackage (clears user data + license cache) ==="
try {
    Get-AppxPackage Claude | Reset-AppxPackage
    Write-Output "RESET OK"
} catch {
    Write-Output ("RESET FAILED: " + $_.Exception.Message)
}

Write-Output ""
Write-Output "=== Step 3: Re-launch test ==="
Start-Sleep -Seconds 3
try {
    Start-Process 'shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude'
    Write-Output "Launch issued"
} catch {
    Write-Output ("Launch failed: " + $_.Exception.Message)
}

Start-Sleep -Seconds 8

Write-Output ""
Write-Output "=== Step 4: Check for running Claude desktop process ==="
$procs = Get-Process | Where-Object { $_.Path -like '*WindowsApps*Claude*' }
if ($procs) {
    Write-Output "DESKTOP APP RUNNING:"
    $procs | Select-Object Id,ProcessName,Path | Format-List
} else {
    Write-Output "DESKTOP APP NOT RUNNING after launch attempt"
}

Write-Output ""
Write-Output "=== Step 5: Latest activation event ==="
$ev = Get-WinEvent -LogName 'Microsoft-Windows-TWinUI/Operational' -MaxEvents 5 -EA SilentlyContinue |
    Where-Object { $_.Message -match 'Claude' } | Select-Object -First 1
if ($ev) {
    Write-Output ("Latest: [" + $ev.TimeCreated + "] " + $ev.Id)
    Write-Output ($ev.Message.Substring(0, [Math]::Min(300, $ev.Message.Length)))
}
