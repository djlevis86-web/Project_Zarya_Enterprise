param(
    [string]$ProjectRoot = "D:\Project_Zarya"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Project Zarya preflight check ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

Set-Location $ProjectRoot

# ---------------------------------------------------------
# 1. Git status
# ---------------------------------------------------------

Write-Host "1. Git status" -ForegroundColor Yellow
git status --short --branch
Write-Host ""

# ---------------------------------------------------------
# 2. Check conflict markers
# ---------------------------------------------------------

Write-Host "2. Checking Git conflict markers..." -ForegroundColor Yellow

$excludeDirs = @(
    ".git",
    "venv",
    ".venv",
    "env",
    "ENV",
    "node_modules",
    "media",
    "backups",
    "backups_db",
    "backups_media",
    "staticfiles",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache"
)

$conflicts = Get-ChildItem -Path $ProjectRoot -Recurse -File |
    Where-Object {
        $file = $_.FullName

        -not ($excludeDirs | Where-Object {
            $file -match "\\$([regex]::Escape($_))(\\|$)"
        })
    } |
    Select-String -Pattern "^\s*(<<<<<<<|=======$|>>>>>>>|\|\|\|\|\|\|\|)" |
    Select-Object Path, LineNumber, Line

if ($conflicts) {
    Write-Host ""
    Write-Host "ERROR: Git conflict markers found:" -ForegroundColor Red
    $conflicts | Format-Table -AutoSize

    exit 1
}

Write-Host "OK: no conflict markers found." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------
# 3. Check dangerous tracked files
# ---------------------------------------------------------

Write-Host "3. Checking dangerous tracked files..." -ForegroundColor Yellow

$dangerousFiles = @(
    "db.sqlite3",
    ".env",
    "counterparties_1c.xlsx",
    "counterparty_candidates_1c.xlsx",
    "redis_inspect.json"
)

$dangerousDirs = @(
    "media",
    "backups",
    "backups_db",
    "backups_media"
)

$trackedDangerous = @()

foreach ($item in $dangerousFiles) {
    $result = git ls-files $item

    if ($result) {
        $trackedDangerous += $result
    }
}

foreach ($item in $dangerousDirs) {
    $result = git ls-files $item

    if ($result) {
        $trackedDangerous += $result
    }
}

if ($trackedDangerous) {
    Write-Host ""
    Write-Host "ERROR: dangerous files are tracked by Git:" -ForegroundColor Red

    $trackedDangerous | ForEach-Object {
        Write-Host $_ -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "Remove them from Git index, for example:" -ForegroundColor Yellow
    Write-Host "git rm --cached <file>" -ForegroundColor Yellow

    exit 1
}

Write-Host "OK: no dangerous tracked files found." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------
# 4. Django check
# ---------------------------------------------------------

Write-Host "4. Django check..." -ForegroundColor Yellow

python manage.py check

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Django check failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OK: Django check passed." -ForegroundColor Green

# ---------------------------------------------------------
# Done
# ---------------------------------------------------------

Write-Host ""
Write-Host "=== Preflight completed successfully ===" -ForegroundColor Green