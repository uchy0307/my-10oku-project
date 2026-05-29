$ErrorActionPreference = 'Stop'
try {
    $task = Get-ScheduledTask -TaskName 'UchyDailyCycle' -EA Stop
    $newTrigger = New-ScheduledTaskTrigger -Daily -At 9:05AM
    Set-ScheduledTask -TaskName 'UchyDailyCycle' -Trigger $newTrigger
    Write-Output "CHANGE OK - new start time: 09:05"
    $t = Get-ScheduledTask -TaskName 'UchyDailyCycle'
    Write-Output ("Next run: " + (Get-ScheduledTaskInfo -TaskName 'UchyDailyCycle').NextRunTime)
} catch {
    Write-Output ("FAILED: " + $_.Exception.Message)
    exit 1
}
