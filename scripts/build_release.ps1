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
    --noupx `
    --icon "blaster\icon.ico" `
    --add-data "blaster\icon.png;blaster" `
    --name Blaster `
    run_game.py | Out-Host

if (-not (Test-Path "dist\Blaster.exe")) {
    throw "Build failed: dist\Blaster.exe not found."
}

$signCertSha1 = $env:BLASTER_SIGN_CERT_SHA1
$signToolPath = $env:BLASTER_SIGNTOOL
if ($signToolPath) {
    $signTool = Get-Command $signToolPath -ErrorAction SilentlyContinue
} else {
    $signTool = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
}

if ($signCertSha1 -and $signTool) {
    Write-Host "Signing Blaster.exe..."
    & $signTool.Source sign `
        /fd SHA256 `
        /td SHA256 `
        /tr "http://timestamp.digicert.com" `
        /sha1 $signCertSha1 `
        "dist\Blaster.exe" | Out-Host
} else {
    Write-Warning "Blaster.exe is unsigned. Windows Defender SmartScreen may block unsigned or low-reputation downloads."
    Write-Warning "Set BLASTER_SIGN_CERT_SHA1 and optionally BLASTER_SIGNTOOL to sign release builds."
}

Write-Host "[5/5] Packing release zip..."
New-Item -ItemType Directory -Path "release\package" -Force | Out-Null
Copy-Item "dist\Blaster.exe" "release\package\Blaster.exe" -Force
Copy-Item "README.md" "release\package\README.md" -Force
Copy-Item "LICENSE" "release\package\LICENSE" -Force
Copy-Item "COPYRIGHT" "release\package\COPYRIGHT" -Force
Copy-Item "CHANGELOG.md" "release\package\CHANGELOG.md" -Force
Copy-Item "docs\WINDOWS_DISTRIBUTION.md" "release\package\WINDOWS_DISTRIBUTION.md" -Force

$exeHash = (Get-FileHash "release\package\Blaster.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
"$exeHash  Blaster.exe" | Set-Content "release\package\SHA256SUMS.txt" -Encoding ASCII

Compress-Archive -Path "release\package\*" -DestinationPath "release\Blaster-windows-x64.zip" -Force

$zipHash = (Get-FileHash "release\Blaster-windows-x64.zip" -Algorithm SHA256).Hash.ToLowerInvariant()
@(
    "$exeHash  package/Blaster.exe",
    "$zipHash  Blaster-windows-x64.zip"
) | Set-Content "release\SHA256SUMS.txt" -Encoding ASCII

Write-Host "Done: release\Blaster-windows-x64.zip"
Write-Host "Checksums: release\SHA256SUMS.txt"
