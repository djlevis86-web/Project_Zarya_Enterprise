param(
    [int]$Limit = 5,
    [int]$IntervalSeconds = 30,
    [switch]$RunOnce
)

$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

$PythonCandidates = @()

if ($env:VIRTUAL_ENV) {
    $PythonCandidates += "$env:VIRTUAL_ENV\Scripts\python.exe"
}

$PythonCandidates += "$ProjectRoot\.venv\Scripts\python.exe"
$PythonCandidates += "$ProjectRoot\venv\Scripts\python.exe"
$PythonCandidates += "python"

$PythonPath = $null

foreach ($candidate in $PythonCandidates) {

    if ($candidate -ne "python" -and -not (Test-Path $candidate)) {
        continue
    }

    & $candidate -c "import django" 2>$null

    if ($LASTEXITCODE -eq 0) {
        $PythonPath = $candidate
        break
    }
}

if (-not $PythonPath) {
    Write-Host "ERROR: Python с установленным Django не найден." -ForegroundColor Red
    Write-Host "Проверь активное виртуальное окружение и requirements." -ForegroundColor Red
    exit 1
}

Write-Host "=== Project Zarya OCR Worker ==="
Write-Host "Project: $ProjectRoot"
Write-Host "Python:  $PythonPath"
Write-Host "Limit:   $Limit"
Write-Host "Delay:   $IntervalSeconds sec"
Write-Host ""

while ($true) {

    $startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Write-Host "[$startedAt] Processing OCR queue..."

    & $PythonPath manage.py process_ocr_queue --limit $Limit

    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Write-Host "OCR worker command failed. Exit code: $exitCode" -ForegroundColor Red
    }

    if ($RunOnce) {
        break
    }

    Write-Host "Waiting $IntervalSeconds seconds..."
    Write-Host ""

    Start-Sleep -Seconds $IntervalSeconds
}