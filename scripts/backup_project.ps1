param(
    [string]$ProjectRoot = "D:\Project_Zarya"
)

$ErrorActionPreference = "Stop"

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$BackupRoot = Join-Path $ProjectRoot "backups"
$TempRoot = Join-Path $env:TEMP "Project_Zarya_backup_$Timestamp"
$ArchivePath = Join-Path $BackupRoot "Project_Zarya_backup_$Timestamp.zip"

Write-Host "=== Project Zarya backup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host "Backup:  $ArchivePath"

if (!(Test-Path $ProjectRoot)) {
    throw "Project folder not found: $ProjectRoot"
}

New-Item $BackupRoot -ItemType Directory -Force | Out-Null

if (Test-Path $TempRoot) {
    Remove-Item $TempRoot -Recurse -Force
}

New-Item $TempRoot -ItemType Directory -Force | Out-Null

$ExcludeDirs = @(
    "venv",
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "backups",
    "staticfiles"
)

$ExcludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    "*.sqlite3-journal",
    "db.sqlite3-journal"
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

Write-Host "Copying project files..." -ForegroundColor Yellow

& robocopy @RobocopyArgs

$RobocopyExitCode = $LASTEXITCODE

if ($RobocopyExitCode -gt 7) {
    throw "Robocopy failed with code $RobocopyExitCode"
}

Write-Host "Creating archive..." -ForegroundColor Yellow

if (Test-Path $ArchivePath) {
    Remove-Item $ArchivePath -Force
}

Compress-Archive `
    -Path (Join-Path $TempRoot "*") `
    -DestinationPath $ArchivePath `
    -CompressionLevel Optimal

Remove-Item $TempRoot -Recurse -Force

$ArchiveSizeMb = [math]::Round((Get-Item $ArchivePath).Length / 1MB, 2)

Write-Host ""
Write-Host "Backup created successfully:" -ForegroundColor Green
Write-Host $ArchivePath
Write-Host "Size: $ArchiveSizeMb MB"