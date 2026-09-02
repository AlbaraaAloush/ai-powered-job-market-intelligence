param(
    [switch]$ProductionFrontend,
    [switch]$WithRag
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunDirectory = Join-Path $ProjectRoot ".run"
$Manifest = Join-Path $ProjectRoot "frontend\public\data\dashboard\manifest.json"

New-Item -ItemType Directory -Force -Path $RunDirectory | Out-Null

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "Static dashboard data is missing. Run .\scripts\build-dashboard-data.ps1 once, then retry."
}

Write-Host "[1/2] Static dashboard snapshot is ready." -ForegroundColor Cyan

Write-Host "[2/2] Starting frontend..." -ForegroundColor Cyan
if (-not (Test-Port 3000)) {
    $FrontendCommand = if ($ProductionFrontend) { "start" } else { "dev" }
    Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList "run", $FrontendCommand `
        -WorkingDirectory (Join-Path $ProjectRoot "frontend") `
        -RedirectStandardOutput (Join-Path $RunDirectory "frontend.log") `
        -RedirectStandardError (Join-Path $RunDirectory "frontend-error.log") `
        -WindowStyle Hidden
} else {
    Write-Host "Frontend is already listening on port 3000."
}

$FrontendReady = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    $StatusCode = curl.exe --max-time 5 --silent --output NUL --write-out "%{http_code}" "http://localhost:3000/app"
    if ($LASTEXITCODE -eq 0 -and $StatusCode -eq "200") {
        $FrontendReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $FrontendReady) {
    throw "Frontend did not start. Check .run/frontend-error.log."
}

Write-Host ""
Write-Host "Dashboard is running without Docker or RAG." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:3000/app"

if ($WithRag) {
    Write-Host ""
    Write-Host "Starting the optional local RAG backend..." -ForegroundColor Cyan
    if (-not (Test-Port 8000)) {
        Start-Process `
            -FilePath (Join-Path $ProjectRoot ".venv\Scripts\python.exe") `
            -ArgumentList "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory (Join-Path $ProjectRoot "RAG") `
            -RedirectStandardOutput (Join-Path $RunDirectory "backend.log") `
            -RedirectStandardError (Join-Path $RunDirectory "backend-error.log") `
            -WindowStyle Hidden
    } else {
        Write-Host "Backend is already listening on port 8000."
    }

    $ApiReady = $false
    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        try {
            $Health = Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 5
            if ($Health.rag_status -eq "ready") {
                $ApiReady = $true
                break
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ApiReady) {
        throw "Full RAG did not become ready. Check .run/backend-error.log."
    }

    Write-Host "Chat:      http://localhost:3000/app/chat"
    Write-Host "Backend:   http://localhost:8000"
    Write-Host "RAG state: $($Health.rag_status)"
}

Write-Host ""
Write-Host "Excel is not processed during dashboard startup."
Write-Host "Rebuild the snapshot only after source data changes: .\scripts\build-dashboard-data.ps1"
