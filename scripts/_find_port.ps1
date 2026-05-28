$pid7373 = (Get-NetTCPConnection -LocalPort 7373 -State Listen -EA SilentlyContinue).OwningProcess
Write-Host ("PID: " + $pid7373)
if ($pid7373) {
    Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pid7373) | Select-Object ProcessId,Name,ExecutablePath,CommandLine | Format-List
}
