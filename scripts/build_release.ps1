param(
    [string]$Python = "python",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

Write-Host "[1/5] Installing build dependencies..."
& $Python -m pip install --upgrade pip | Out-Host
& $Python -m pip install -r requirements.txt pyinstaller | Out-Host

if (-not $SkipTests) {
    Write-Host "[2/5] Running tests..."
    & $Python -m pytest -q | Out-Host
} else {
    Write-Host "[2/5] Tests skipped by flag."
}

Write-Host "[3/5] Cleaning previous build artifacts..."
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path release) { Remove-Item release -Recurse -Force }

Write-Host "[4/5] Building Blaster.exe..."
if (-not (Test-Path "blaster\icon.ico")) {
    throw "Build failed: blaster\icon.ico not found."
}
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --icon "blaster\icon.ico" `
    --add-data "blaster\icon.png;blaster" `
    --name Blaster `
    run_game.py | Out-Host

if (-not (Test-Path "dist\Blaster.exe")) {
    throw "Build failed: dist\Blaster.exe not found."
}

Write-Host "[5/5] Packing release zip..."
New-Item -ItemType Directory -Path "release\package" -Force | Out-Null
Copy-Item "dist\Blaster.exe" "release\package\Blaster.exe" -Force
Copy-Item "README.md" "release\package\README.md" -Force
Copy-Item "LICENSE" "release\package\LICENSE" -Force
Copy-Item "COPYRIGHT" "release\package\COPYRIGHT" -Force
Copy-Item "CHANGELOG.md" "release\package\CHANGELOG.md" -Force

Compress-Archive -Path "release\package\*" -DestinationPath "release\Blaster-windows-x64.zip" -Force

Write-Host "Done: release\Blaster-windows-x64.zip"
