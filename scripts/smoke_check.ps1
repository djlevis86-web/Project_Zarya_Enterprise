$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== Project Zarya smoke check ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

$failed = $false

function Step-Run {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ">>> $Title" -ForegroundColor Yellow

    $global:LASTEXITCODE = 0

    try {
        & $Command

        $exitCode = $LASTEXITCODE

        if ($null -eq $exitCode) {
            $exitCode = 0
        }

        if ($exitCode -ne 0) {
            Write-Host "FAILED: $Title" -ForegroundColor Red
            $script:failed = $true
        } else {
            Write-Host "OK: $Title" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "FAILED: $Title" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        $script:failed = $true
    }

    Write-Host ""
}

Step-Run "Django system check" {
    python manage.py check
}

Step-Run "Migrations check" {
    python manage.py makemigrations --check --dry-run
}

Step-Run "OCR worker one pass" {
    .\scripts\run_ocr_worker.ps1 -RunOnce
}

Step-Run "Static CSS exists" {
    if (-not (Test-Path ".\static\css\style.css")) {
        throw "Missing static/css/style.css"
    }
}

Step-Run "Important templates exist" {
    $files = @(
        ".\templates\base.html",
        ".\templates\dashboard.html",
        ".\templates\profile.html",
        ".\system\templates\system\dashboard.html",
        ".\system\templates\system\backups.html",
        ".\system\templates\system\versions.html",
        ".\system\templates\system\updates.html",
        ".\system\templates\system\maintenance.html"
    )

    foreach ($file in $files) {
        if (-not (Test-Path $file)) {
            throw "Missing: $file"
        }
    }
}

Step-Run "Conflict markers check" {
    $trackedFiles = git ls-files -- `
        "*.py" `
        "*.html" `
        "*.css" `
        "*.js" `
        "*.txt" `
        "*.md" `
        "*.ps1" `
        "*.bat" `
        "*.json" `
        "*.yml" `
        "*.yaml"

    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed."
    }

    if (-not $trackedFiles) {
        return
    }

    $patterns = @(
        '^\s*<{7}.*$',
        '^\s*={7}\s*$',
        '^\s*>{7}.*$'
    )

    $matches = Select-String `
        -Path $trackedFiles `
        -Pattern $patterns `
        -ErrorAction SilentlyContinue

    if ($matches) {
        $matches | Select-Object Path, LineNumber, Line
        throw "Conflict markers found."
    }

    $global:LASTEXITCODE = 0
}

if ($failed) {
    Write-Host "=== Smoke check failed ===" -ForegroundColor Red
    exit 1
}

Write-Host "=== Smoke check completed successfully ===" -ForegroundColor Green
exit 0
