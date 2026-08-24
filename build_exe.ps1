$ErrorActionPreference = "Stop"
$python = "C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}
$buildDir = Join-Path $env:TEMP "dlcp_batch_ascii_build"
$distDir = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "dlcp_gui.py") -Destination (Join-Path $buildDir "dlcp_gui.py") -Force
Push-Location $buildDir
try {
    & $python -m PyInstaller --noconfirm --clean --onefile --windowed --name DLCP_Batch_Analyzer --distpath $distDir --workpath (Join-Path $buildDir "work") --specpath $buildDir dlcp_gui.py
}
finally {
    Pop-Location
}
Write-Host "EXE created under $distDir\DLCP_Batch_Analyzer.exe"
