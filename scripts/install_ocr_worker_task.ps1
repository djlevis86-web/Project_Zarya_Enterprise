param(
    [int]$Limit = 5,
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"

$TaskName = "Project Zarya OCR Worker"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkerScript = Join-Path $ProjectRoot "scripts\run_ocr_worker.ps1"
$UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path $WorkerScript)) {
    Write-Host "ERROR: Worker script not found: $WorkerScript" -ForegroundColor Red
    exit 1
}

$Argument = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$WorkerScript`" -Limit $Limit -IntervalSeconds $IntervalSeconds"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $Argument `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -AtLogOn

$Principal = New-ScheduledTaskPrincipal `
    -UserId $UserId `
    -LogonType Interactive `
    -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Project Zarya OCR queue background worker"

Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $Task `
    -Force | Out-Null

Write-Host "OCR worker task installed." -ForegroundColor Green
Write-Host "Task: $TaskName"
Write-Host "User: $UserId"
Write-Host "Project: $ProjectRoot"
Write-Host "Worker: $WorkerScript"

Start-ScheduledTask `
    -TaskName $TaskName

Start-Sleep -Seconds 2

Get-ScheduledTask `
    -TaskName $TaskName

Get-ScheduledTaskInfo `
    -TaskName $TaskName

