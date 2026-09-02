$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found at $Python"
}

& $Python (Join-Path $ProjectRoot "RAG\build_static_dashboard.py")
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard data build failed with exit code $LASTEXITCODE."
}

Write-Host "Static dashboard data is ready for local use and Vercel deployment." -ForegroundColor Green
