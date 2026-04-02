param(
    [string]$EngRoot = $(Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "wireless-mic-battery-alert-eng"),
    [string]$OutputRoot = $(Join-Path $env:USERPROFILE "wireless-mic-battery-alert-build")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EngRoot)) {
    throw "Eng repository not found: $EngRoot"
}

Write-Host "Eng root: $EngRoot"
Set-Location $EngRoot

if (-not (Test-Path $OutputRoot)) {
    New-Item -ItemType Directory -Path $OutputRoot | Out-Null
}

$workPath = Join-Path $OutputRoot "build"
$distPath = Join-Path $OutputRoot "dist"

Write-Host "Output root: $OutputRoot"

Write-Host "Python version:"
python --version

Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt

Write-Host "Running PyInstaller build..."
python -m PyInstaller build.spec --noconfirm --clean --distpath $distPath --workpath $workPath

$distRoot = Join-Path $distPath "WirelessMicBatteryAlert"
$exePath = Join-Path $distRoot "WirelessMicBatteryAlert.exe"
$assetsRoot = Join-Path $distRoot "_internal\assets"

if (-not (Test-Path $exePath)) {
    throw "Expected EXE not found: $exePath"
}

Write-Host "Build output:"
Get-ChildItem $distRoot

Write-Host "Bundled assets:"
Get-ChildItem $assetsRoot

Write-Host "Build completed successfully."
Write-Host "EXE: $exePath"
