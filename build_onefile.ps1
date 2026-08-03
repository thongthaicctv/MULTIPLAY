$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectDir

Write-Host "=== ATG MultiPlay - Build One File ===" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath ".\main.py")) {
    throw "Khong tim thay main.py."
}

if (-not (Test-Path -LiteralPath ".\icon.ico")) {
    throw "Khong tim thay icon.ico."
}

if (-not (Test-Path -LiteralPath ".\antn.png")) {
    throw "Khong tim thay antn.png."
}

if (-not (Test-Path -LiteralPath ".\bin\ffmpeg.exe")) {
    throw "Khong tim thay bin\ffmpeg.exe."
}

if (-not (Test-Path -LiteralPath ".\bin\ffprobe.exe")) {
    Write-Warning "Khong tim thay bin\ffprobe.exe. EXE van ghep duoc video nhung khong co metadata chinh xac."
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    throw "Khong tim thay Python trong PATH. Hay kich hoat moi truong .venv truoc khi build."
}

python -c "import PyInstaller, PyQt6, pymysql, requests, av, numpy, vlc"
if ($LASTEXITCODE -ne 0) {
    throw "Thieu dependency. Chay: pip install -r requirements.txt"
}

python -m PyInstaller --noconfirm --clean ".\ATG-MultiPlay.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build that bai."
}

$OutputFile = Join-Path $ProjectDir "dist\ATG-MultiPlay.exe"
if (-not (Test-Path -LiteralPath $OutputFile)) {
    throw "Build hoan tat nhung khong tim thay dist\ATG-MultiPlay.exe."
}

$SizeMb = [math]::Round((Get-Item -LiteralPath $OutputFile).Length / 1MB, 2)
Write-Host ""
Write-Host "BUILD THANH CONG" -ForegroundColor Green
Write-Host "File: $OutputFile"
Write-Host "Dung luong: $SizeMb MB"
Write-Host "Luu y: dat config.json canh file EXE khi chay tren may dich." -ForegroundColor Yellow
