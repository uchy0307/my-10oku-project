$d = Get-PSDrive -Name C
$usedGB = [Math]::Round($d.Used / 1GB, 2)
$freeGB = [Math]::Round($d.Free / 1GB, 2)
$totalGB = [Math]::Round(($d.Used + $d.Free) / 1GB, 2)
Write-Output ("C:_TOTAL_GB=" + $totalGB)
Write-Output ("C:_USED_GB="  + $usedGB)
Write-Output ("C:_FREE_GB="  + $freeGB)
if ($freeGB -lt 2.0) {
    Write-Output "STATUS=CRITICAL_under_2GB"
} elseif ($freeGB -lt 5.0) {
    Write-Output "STATUS=WARNING_under_5GB"
} else {
    Write-Output "STATUS=OK"
}
