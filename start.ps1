<#
.SYNOPSIS
    Start the Life Graph application (backend + dashboard).

.DESCRIPTION
    1. Rebuilds and starts the Docker backend (API, worker, Postgres, Redis, MinIO, MCP)
    2. Runs Alembic migrations to ensure DB is up to date
    3. Starts the Next.js dashboard dev server

.EXAMPLE
    .\start.ps1           # Start everything
    .\start.ps1 -Backend  # Start only backend (Docker)
    .\start.ps1 -Dashboard # Start only dashboard (Next.js)
#>
param(
    [switch]$Backend,
    [switch]$Dashboard,
    [switch]$NoBuild   # Skip Docker rebuild (faster restart)
)

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Life Graph — Starting..." -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor DarkCyan
Write-Host ""

# If neither flag is set, start both
$startBoth = -not $Backend -and -not $Dashboard

# ── Backend (Docker Compose) ──────────────────────────────
if ($Backend -or $startBoth) {
    Write-Host "[1/4] Starting Docker backend..." -ForegroundColor Yellow

    Push-Location $ROOT

    if (-not $NoBuild) {
        Write-Host "  Building containers..." -ForegroundColor DarkGray
        docker compose build --quiet 2>&1 | Out-Null
    }

    Write-Host "  Starting containers..." -ForegroundColor DarkGray
    docker compose up -d 2>&1 | ForEach-Object {
        if ($_ -match "Started|Running|Created") { Write-Host "  $_" -ForegroundColor DarkGreen }
    }

    # Wait for backend health
    Write-Host "[2/4] Waiting for backend..." -ForegroundColor Yellow -NoNewline
    $attempts = 0
    $healthy = $false
    while ($attempts -lt 30) {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {}
        Write-Host "." -NoNewline -ForegroundColor DarkGray
        $attempts++
    }

    if ($healthy) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " TIMEOUT (backend may still be starting)" -ForegroundColor Red
    }

    # Run migrations
    Write-Host "[3/4] Running migrations..." -ForegroundColor Yellow
    $migResult = python -m alembic upgrade head 2>&1
    $currentRev = python -m alembic current 2>&1 | Select-String "^\d+" | ForEach-Object { $_.Matches[0].Value }
    Write-Host "  Database at revision: $currentRev" -ForegroundColor DarkGreen

    Pop-Location
}

# ── Dashboard (Next.js dev server) ────────────────────────
if ($Dashboard -or $startBoth) {
    Write-Host "[4/4] Starting dashboard..." -ForegroundColor Yellow

    $dashDir = Join-Path $ROOT "dashboard"
    if (-not (Test-Path (Join-Path $dashDir "node_modules"))) {
        Write-Host "  Installing dependencies..." -ForegroundColor DarkGray
        Push-Location $dashDir
        $env:TEMP = "D:\npm-tmp"; $env:TMP = "D:\npm-tmp"
        npm install --silent 2>&1 | Out-Null
        Pop-Location
    }

    # Start dev server in background
    $env:TEMP = "D:\npm-tmp"; $env:TMP = "D:\npm-tmp"
    Start-Process powershell -ArgumentList "-NoProfile", "-Command", "Set-Location '$dashDir'; `$env:TEMP='D:\npm-tmp'; `$env:TMP='D:\npm-tmp'; npm run dev" -WindowStyle Minimized
    Write-Host "  Dashboard starting at http://localhost:3000" -ForegroundColor DarkGreen
}

# ── Summary ───────────────────────────────────────────────
Write-Host ""
Write-Host "  ✅ Life Graph is running!" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:     http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Dashboard:    http://localhost:3000" -ForegroundColor White
Write-Host "  WebSocket:    ws://localhost:8000/ws" -ForegroundColor White
Write-Host "  MCP Server:   http://localhost:8001" -ForegroundColor DarkGray
Write-Host "  MinIO:        http://localhost:9001" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Stop with: .\stop.ps1" -ForegroundColor DarkGray
Write-Host ""
