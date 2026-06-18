param(
    [string]$ProjectRoot = "D:\Project_Zarya"
)

$ErrorActionPreference = "Stop"

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

$BackupRoot = Join-Path $ProjectRoot "backups"
$DbBackupRoot = Join-Path $ProjectRoot "backups_db"
$MediaBackupRoot = Join-Path $ProjectRoot "backups_media"

$TempRoot = Join-Path $env:TEMP "Project_Zarya_full_backup_$Timestamp"

$ProjectArchive = Join-Path $BackupRoot "Project_Zarya_code_$Timestamp.zip"
$DbArchive = Join-Path $DbBackupRoot "db_$Timestamp.sqlite3"
$MediaArchive = Join-Path $MediaBackupRoot "media_$Timestamp.zip"

Write-Host "=== Project Zarya backup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

New-Item $BackupRoot -ItemType Directory -Force | Out-Null
New-Item $DbBackupRoot -ItemType Directory -Force | Out-Null
New-Item $MediaBackupRoot -ItemType Directory -Force | Out-Null

if (Test-Path $TempRoot) {
    Remove-Item $TempRoot -Recurse -Force
}

New-Item $TempRoot -ItemType Directory -Force | Out-Null

Write-Host ""
Write-Host "1. Database backup..." -ForegroundColor Yellow

$DbFile = Join-Path $ProjectRoot "db.sqlite3"

if (Test-Path $DbFile) {
    Copy-Item $DbFile $DbArchive -Force
    Write-Host "DB backup created: $DbArchive" -ForegroundColor Green
} else {
    Write-Host "DB file not found: $DbFile" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. Media backup..." -ForegroundColor Yellow

$MediaRoot = Join-Path $ProjectRoot "media"

if (Test-Path $MediaRoot) {
    if (Test-Path $MediaArchive) {
        Remove-Item $MediaArchive -Force
    }

    Compress-Archive `
        -Path (Join-Path $MediaRoot "*") `
        -DestinationPath $MediaArchive `
        -CompressionLevel Optimal

    Write-Host "Media backup created: $MediaArchive" -ForegroundColor Green
} else {
    Write-Host "Media folder not found: $MediaRoot" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "3. Code backup..." -ForegroundColor Yellow

$ExcludeDirs = @(
    ".git",
    "venv",
    ".venv",
    "env",
    "ENV",
    "__pycache__",
    "node_modules",
    "media",
    "backups",
    "backups_db",
    "backups_media",
    "staticfiles",
    ".pytest_cache",
    ".mypy_cache"
)

$ExcludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    "*.bak",
    "*.backup",
    "*.broken_backup",
    "db.sqlite3",
    "db.sqlite3-journal",
    ".env",
    "counterparties_1c.xlsx",
    "counterparty_candidates_1c.xlsx",
    "redis_inspect.json"
)

$RobocopyArgs = @(
    $ProjectRoot,
    $TempRoot,
    "/E",
    "/R:2",
    "/W:2",
    "/NFL",
    "/NDL",
    "/NP"
)

foreach ($dir in $ExcludeDirs) {
    $RobocopyArgs += "/XD"
    $RobocopyArgs += (Join-Path $ProjectRoot $dir)
}

foreach ($file in $ExcludeFiles) {
    $RobocopyArgs += "/XF"
    $RobocopyArgs += $file
}

& robocopy @RobocopyArgs

$RobocopyExitCode = $LASTEXITCODE

if ($RobocopyExitCode -gt 7) {
    throw "Robocopy failed with code $RobocopyExitCode"
}

if (Test-Path $ProjectArchive) {
    Remove-Item $ProjectArchive -Force
}

Compress-Archive `
    -Path (Join-Path $TempRoot "*") `
    -DestinationPath $ProjectArchive `
    -CompressionLevel Optimal

Remove-Item $TempRoot -Recurse -Force

Write-Host "Code backup created: $ProjectArchive" -ForegroundColor Green

Write-Host ""
Write-Host "=== Backup completed ===" -ForegroundColor Green
Write-Host "Code:  $ProjectArchive"
Write-Host "DB:    $DbArchive"
Write-Host "Media: $MediaArchive"