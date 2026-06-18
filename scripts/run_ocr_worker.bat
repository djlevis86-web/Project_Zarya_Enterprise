@echo off
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_ocr_worker.ps1" -Limit 5 -IntervalSeconds 30

pause
