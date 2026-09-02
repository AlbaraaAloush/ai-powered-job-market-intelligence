param(
    [switch]$IncludeRag,
    [switch]$IncludeLiveRag
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Failures = [System.Collections.Generic.List[string]]::new()

function Run-Check([string]$Name, [scriptblock]$Command) {
    Write-Host "`n== $Name ==" -ForegroundColor Cyan
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) { throw "Exit code $LASTEXITCODE" }
        Write-Host "PASS: $Name" -ForegroundColor Green
    } catch {
        Write-Host "FAIL: $Name - $($_.Exception.Message)" -ForegroundColor Red
        $Failures.Add($Name)
    }
}

Run-Check "Static dashboard runtime" {
    $Frontend = curl.exe --max-time 15 --silent --output NUL --write-out "%{http_code}" "http://localhost:3000/app"
    $Manifest = Invoke-RestMethod "http://localhost:3000/data/dashboard/manifest.json" -TimeoutSec 15
    if ($Frontend -ne "200") { throw "Frontend returned HTTP $Frontend" }
    if ($Manifest.record_count -lt 1) { throw "Static manifest contains no records" }
    if (-not $Manifest.analytics_file) { throw "Static manifest has no analytics file" }
    $Manifest | Select-Object schema_version, data_version, record_count, generated_at | Format-List
}

Run-Check "Static dashboard files" {
    $ManifestPath = Join-Path $ProjectRoot "frontend\public\data\dashboard\manifest.json"
    $Manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
    $AnalyticsPath = Join-Path (Split-Path $ManifestPath) $Manifest.analytics_file
    if (-not (Test-Path -LiteralPath $AnalyticsPath)) { throw "Missing $AnalyticsPath" }
    foreach ($Filename in $Manifest.posting_files.PSObject.Properties.Value) {
        $DetailPath = Join-Path (Split-Path $ManifestPath) $Filename
        if (-not (Test-Path -LiteralPath $DetailPath)) { throw "Missing $DetailPath" }
    }
}

Run-Check "Frontend lint" {
    Push-Location (Join-Path $ProjectRoot "frontend")
    try { npm run lint } finally { Pop-Location }
}

Run-Check "Frontend production build" {
    Push-Location (Join-Path $ProjectRoot "frontend")
    try { npm run build } finally { Pop-Location }
}

if ($IncludeRag -or $IncludeLiveRag) {
    Run-Check "Optional RAG backend" {
        $Health = Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 20
        if ($Health.status -ne "ok") { throw "Backend is not healthy" }
        if ($Health.storage.status -ne "ok") { throw "RAG storage is not healthy" }
        $Health | Select-Object status, rag_status, postings, vectors, storage | Format-List
    }

    Run-Check "Backend unit tests" {
        & $Python -m pytest (Join-Path $ProjectRoot "RAG\tests") -q --ignore=(Join-Path $ProjectRoot "RAG\tests\test_live_api.py")
    }
}

if ($IncludeLiveRag) {
    Run-Check "Live English/Arabic RAG benchmark (uses LLM credits)" {
        & $Python (Join-Path $ProjectRoot "RAG\evaluate_live_pipeline.py") --base-url http://localhost:8000
    }
} elseif (-not $IncludeRag) {
    Write-Host "`nRAG checks skipped. Use -IncludeRag after starting with -WithRag." -ForegroundColor Yellow
}

Write-Host ""
if ($Failures.Count -gt 0) {
    Write-Host "FAILED CHECKS: $($Failures -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "ALL REQUESTED CHECKS PASSED." -ForegroundColor Green
