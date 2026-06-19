# PentraCe — masaustu .exe build scripti (Windows).
# Frontend'i build eder, ardindan PyInstaller ile tek dosya PentraCe.exe uretir.
# Kullanim:  .\build-desktop.ps1            (pencereli/uretim)
#            .\build-desktop.ps1 -Console   (konsollu/hata ayiklama)

param([switch]$Console)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Backend venv yok. Once:  cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt pywebview pyinstaller pillow" -ForegroundColor Yellow
    exit 1
}

# 1) Frontend build
Write-Host "[1/2] Frontend build ediliyor..." -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location

# 2) PyInstaller
Write-Host "[2/2] PentraCe.exe paketleniyor (birkac dakika)..." -ForegroundColor Cyan
Push-Location $backend
$consoleFlag = if ($Console) { "--console" } else { "--windowed" }
& $py -m PyInstaller --noconfirm --onefile --name PentraCe $consoleFlag `
    --icon pentrace.ico `
    --add-data "../frontend/dist;frontend/dist" `
    --add-data "wordlists;backend/wordlists" `
    --collect-all webview `
    --collect-all reportlab `
    --collect-submodules uvicorn `
    --collect-submodules sqlalchemy `
    --hidden-import aiosqlite `
    --hidden-import greenlet `
    --hidden-import report `
    --hidden-import email_service `
    desktop.py
Pop-Location

$exe = Join-Path $backend "dist\PentraCe.exe"
if (Test-Path $exe) {
    $mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "`nTamam! -> $exe ($mb MB)" -ForegroundColor Green
    Write-Host "Cift tikla calistir. Veri: %APPDATA%\PentraCe (DB + raporlar)." -ForegroundColor Green
} else {
    Write-Host "Build basarisiz — cikti exe bulunamadi." -ForegroundColor Red
    exit 1
}
