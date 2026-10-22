# geodoc — build the installer payload (automates docs/PACKAGING.md).
# Produces installer/python-embed (embeddable runtime + vendored wheels +
# pre-cached OCR models) and installer/llama-bin/<build>, then compiles
# setup.exe with the model bundled when Inno Setup (iscc) is available.
# Code signing stays manual.
#
# Usage: powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1
#        [-LlamaDir <folder with llama-server.exe>] [-ModelDir <folder with the GGUF>]
# Defaults are the layout tools/fetch_runtime.py writes into the clone.

param(
    [string]$LlamaDir = (Join-Path (Split-Path $PSScriptRoot -Parent) "llama-bin\b10155"),
    [string]$ModelDir = (Join-Path (Split-Path $PSScriptRoot -Parent) "models")
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$inst = Join-Path $root "installer"
$py   = Join-Path $inst "python-embed"
$pyver = "3.12.8"

Write-Host "[1/6] python embeddable $pyver"
if (-not (Test-Path (Join-Path $py "python.exe"))) {
    $zip = Join-Path $env:TEMP "python-embed-$pyver.zip"
    if (-not (Test-Path $zip)) {
        Invoke-WebRequest "https://www.python.org/ftp/python/$pyver/python-$pyver-embed-amd64.zip" -OutFile $zip
    }
    Expand-Archive $zip -DestinationPath $py -Force
    $pth = Get-ChildItem $py -Filter "python3*._pth" | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '#import site', 'import site' |
        Set-Content $pth.FullName
}

Write-Host "[2/6] vendor wheels into site-packages (dev python --target)"
$site = Join-Path $py "Lib\site-packages"
New-Item -ItemType Directory -Force $site | Out-Null
python -m pip install -r (Join-Path $root "requirements.txt") `
    --target $site --quiet --upgrade

Write-Host "[3/6] pre-cache OCR models inside the payload"
& (Join-Path $py "python.exe") -c "from rapidocr import RapidOCR; RapidOCR(); print('rapidocr models cached')"

Write-Host "[4/6] llama.cpp binaries (runtime CPU dispatch dlls)"
# the build number stays in the path: the reproducibility seal records the
# server's parent folder name as the engine build
$build = Split-Path $LlamaDir -Leaf
if ($build -notlike "b*") { throw "LlamaDir must end in the build folder, e.g. llama-bin\b10155" }
$lb = Join-Path (Join-Path $inst "llama-bin") $build
New-Item -ItemType Directory -Force $lb | Out-Null
Copy-Item (Join-Path $LlamaDir "*") $lb -Force

Write-Host "[5/6] tray shell (rust, self-contained GNU toolchain)"
if (-not (Test-Path (Join-Path $root "src-tauri\geodoc-tray.exe"))) {
    & (Join-Path $PSScriptRoot "build_tray.ps1")
}

Write-Host "[6/6] compile setup.exe (Inno) when available"
# PATH first, then the per-user install location (Inno's default target)
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $p = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path $p) { $iscc = $p }
}
if ($iscc) {
    & $iscc "/DGgufDir=$ModelDir" (Join-Path $inst "geodoc.iss")
    Write-Host "setup.exe + .bin volumes: installer\Output (sign before shipping)"
} else {
    Write-Host "iscc not found - install Inno Setup 6 to compile setup.exe"
}
