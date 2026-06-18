param(
    [string]$ProjectRoot = "D:\Project_Zarya",
    [string]$Message = "Update Project Zarya"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Project Zarya GitHub push ===" -ForegroundColor Cyan

Set-Location $ProjectRoot

if (!(Test-Path ".git")) {
    Write-Host "Git repository not found. Initializing..." -ForegroundColor Yellow

    git init
    git branch -M main
}

$Remote = git remote get-url origin 2>$null

if (!$Remote) {
    Write-Host "Git remote origin is not configured." -ForegroundColor Yellow
    Write-Host "Add remote manually, for example:"
    Write-Host "git remote add origin https://github.com/djlevis86-web/Project_Zarya_Enterprise.git"
    exit 1
}

Write-Host "Checking files..." -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "Adding files..." -ForegroundColor Yellow
git add .

$Changes = git status --porcelain

if (!$Changes) {
    Write-Host "No changes to commit." -ForegroundColor Green
    exit 0
}

Write-Host "Committing..." -ForegroundColor Yellow
git commit -m $Message

Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push

Write-Host ""
Write-Host "Pushed successfully." -ForegroundColor Green