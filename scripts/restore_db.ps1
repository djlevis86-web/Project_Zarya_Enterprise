param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,

    [string]$ProjectRoot = "D:\Project_Zarya"
)

$ErrorActionPreference = "Stop"

$DbFile = Join-Path $ProjectRoot "db.sqlite3"
$BeforeRestore = Join-Path $ProjectRoot ("db_before_restore_" + (Get-Date -Format "yyyy-MM-dd_HH-mm-ss") + ".sqlite3")

if (!(Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

if (Test-Path $DbFile) {
    Copy-Item $DbFile $BeforeRestore -Force
    Write-Host "Current DB saved as: $BeforeRestore" -ForegroundColor Yellow
}

Copy-Item $BackupFile $DbFile -Force

Write-Host "Database restored from:" -ForegroundColor Green
Write-Host $BackupFile