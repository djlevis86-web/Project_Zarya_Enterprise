$ErrorActionPreference = "Continue"

$TaskName = "Project Zarya OCR Worker"

$Task = Get-ScheduledTask `
    -TaskName $TaskName `
    -ErrorAction SilentlyContinue

if (-not $Task) {

    Write-Host "OCR worker task not installed." -ForegroundColor Yellow
    exit 0
}

Get-ScheduledTask `
    -TaskName $TaskName

Get-ScheduledTaskInfo `
    -TaskName $TaskName
