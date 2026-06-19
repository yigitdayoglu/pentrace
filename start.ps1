# PentraCe — backend + frontend'i birlikte baslatir (Windows PowerShell).
# Kullanim:  .\start.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "PentraCe baslatiliyor..." -ForegroundColor Green

# Backend (uvicorn)
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "venv bulunamadi. Once kurulum:" -ForegroundColor Yellow
    Write-Host "  cd backend; py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","main:app","--port","8000" -WorkingDirectory (Join-Path $root "backend")
Write-Host "  Backend  -> http://127.0.0.1:8000  (Swagger: /docs)" -ForegroundColor Cyan

# Frontend (vite)
Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm run dev" -WorkingDirectory (Join-Path $root "frontend")
Write-Host "  Frontend -> http://localhost:5173" -ForegroundColor Cyan

Write-Host "`nIki servis ayri pencerelerde calisiyor. Kapatmak icin pencereleri kapatin." -ForegroundColor Green
