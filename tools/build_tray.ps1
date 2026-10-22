# build_tray.ps1 — builds src-tauri/geodoc-tray.exe on a machine WITHOUT MSVC.
#
# Why the ceremony: rustc's msvc target needs link.exe (Visual Studio C++ tools,
# absent here), and Git-Bash shadows link.exe with coreutils' hard-link tool.
# The self-contained GNU toolchain carries its own ld — but its binutils dlltool
# cannot run (no bundled as.exe), and the windows-* crates need dlltool for
# raw-dylib imports. llvm-ar from the llvm-tools component is a multi-call
# binary: renamed to dlltool.exe it becomes llvm-dlltool, which needs no
# assembler. Run this from PowerShell, never from Git Bash.

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$tc = "stable-x86_64-pc-windows-gnu"
$tcRoot = "$env:USERPROFILE\.rustup\toolchains\$tc\lib\rustlib\x86_64-pc-windows-gnu\bin"

if (-not (Test-Path "$env:USERPROFILE\.rustup\toolchains\$tc")) {
    rustup toolchain install $tc --profile minimal
}
if (-not (Test-Path "$tcRoot\llvm-ar.exe")) {
    rustup component add llvm-tools --toolchain $tc
}

$shim = Join-Path $env:TEMP "geodoc-dlltool-shim"
New-Item -ItemType Directory -Force $shim | Out-Null
Copy-Item "$tcRoot\llvm-ar.exe" "$shim\dlltool.exe" -Force
$env:PATH = "$shim;$env:PATH"

Push-Location "$repo\src-tauri"
try {
    cargo "+$tc" build --release
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed" }
} finally {
    Pop-Location
}

# resource stamp: icon + VersionInfo (no windres/llvm-rc on this toolchain —
# rcedit is the verdict; WHEN Certum signing arrives it must run AFTER this,
# rcedit rewrites the PE and would break an earlier signature)
$exe = "$repo\src-tauri\target\release\geodoc-tray.exe"
$rc = "$repo\tools\bin\rcedit-x64.exe"
if (Test-Path $rc) {
    & $rc $exe --set-icon "$repo\installer\branding\geodoc.ico" `
        --set-version-string CompanyName "Norbert Marchewka" `
        --set-version-string ProductName "geodoc" `
        --set-version-string FileDescription "geodoc — kontrola operatow technicznych" `
        --set-version-string LegalCopyright "(c) 2026 Norbert Marchewka, MIT License" `
        --set-version-string OriginalFilename "geodoc-tray.exe" `
        --set-file-version "0.9.5.0" --set-product-version "0.95"
    if ($LASTEXITCODE -ne 0) { throw "rcedit failed" }
    Write-Host "stamped: icon + VersionInfo"
} else {
    Write-Host "UWAGA: tools\bin\rcedit-x64.exe brak - exe bez ikony/metadanych"
}

# installed layout wants the exe at {app}\src-tauri\geodoc-tray.exe
Copy-Item "$repo\src-tauri\target\release\geodoc-tray.exe" "$repo\src-tauri\geodoc-tray.exe" -Force
$mb = "{0:N1}" -f ((Get-Item "$repo\src-tauri\geodoc-tray.exe").Length / 1MB)
Write-Host "OK: src-tauri\geodoc-tray.exe ($mb MB)"
