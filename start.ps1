<#
.SYNOPSIS
    Start the Life Graph application.
.DESCRIPTION
    Hybrid dev setup optimized for Windows ARM:
    - Postgres + Redis: Docker containers (start once, leave running)
    - Backend API: local uvicorn on :8080 (avoids Docker port conflict)
    - Dashboard: local Next.js dev server on :3000
.EXAMPLE
    .\start.ps1              # Start API + dashboard (assumes Postgres/Redis running)
    .\start.ps1 -All         # Start everything including Postgres/Redis
    .\start.ps1 -Backend     # Start only backend API
    .\start.ps1 -Dashboard   # Start only dashboard
    .\start.ps1 -Infra       # Start only Postgres + Redis
#>
param(
    [switch]$Backend,
    [switch]$Dashboard,
    [switch]$Infra,
    [switch]$All
)

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$API_PORT = 8080

Write-Host ""
Write-Host "  Life Graph - Starting..." -ForegroundColor Cyan
Write-Host ""

# Default: start backend + dashboard
$startBoth = -not $Backend -and -not $Dashboard -and -not $Infra -and -not $All

# ----------------------------------------------------------------
# Infrastructure (Postgres + Redis via Docker)
# ----------------------------------------------------------------
if ($Infra -or $All) {
    Write-Host "[infra] Starting Postgres + Redis..." -ForegroundColor Yellow
    Push-Location $ROOT

    # Only start DB services, not the full compose stack
    $job = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        docker compose up -d postgres redis 2>&1
    } -ArgumentList $ROOT

    $done = Wait-Job $job -Timeout 120
    if ($done) {
        Receive-Job $job | ForEach-Object {
            if ($_ -match "Started|Running|Created|Healthy") { Write-Host "  $_" -ForegroundColor DarkGreen }
        }
    } else {
        Write-Host "  Docker is slow, services may still be starting..." -ForegroundColor Yellow
        Stop-Job $job
    }
    Remove-Job $job -Force -ErrorAction SilentlyContinue

    # Wait for Postgres to be ready
    Write-Host "  Waiting for Postgres..." -ForegroundColor DarkGray -NoNewline
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 2
        if (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue) {
            Write-Host " OK" -ForegroundColor Green; break
        }
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
    Pop-Location
}

# ----------------------------------------------------------------
# Backend API (local uvicorn on $API_PORT)
# ----------------------------------------------------------------
if ($Backend -or $startBoth -or $All) {
    # Check Postgres
    if (-not (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue)) {
        Write-Host "[backend] WARNING: Postgres not running on :5432" -ForegroundColor Red
        Write-Host "  Run: .\start.ps1 -Infra" -ForegroundColor Yellow
        Write-Host ""
    }

    # Free port if occupied by another local process
    $existing = Get-NetTCPConnection -LocalPort $API_PORT -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        $proc = Get-Process -Id $existing.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "[backend] Port :$API_PORT occupied by $($proc.ProcessName), killing..." -ForegroundColor DarkGray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    # Run migrations
    Write-Host "[backend] Running migrations..." -ForegroundColor Yellow
    Push-Location $ROOT
    python -m alembic upgrade head 2>&1 | Out-Null
    $rev = python -m alembic current 2>&1 | Select-String "^\d+" | ForEach-Object { $_.Matches[0].Value }
    Write-Host "  DB at revision: $rev" -ForegroundColor DarkGreen

    # Start uvicorn on $API_PORT
    Write-Host "[backend] Starting uvicorn on :$API_PORT..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-Command",
        "Set-Location '$ROOT'; python -m uvicorn life_graph.main:app --host 0.0.0.0 --port $API_PORT --reload --reload-dir life_graph"
    ) -WindowStyle Minimized
    Pop-Location

    # Wait for health
    Write-Host "  Waiting for API..." -ForegroundColor DarkGray -NoNewline
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$API_PORT/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { Write-Host " OK" -ForegroundColor Green; break }
        } catch {}
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
}

# ----------------------------------------------------------------
# Dashboard (local Next.js)
# ----------------------------------------------------------------
if ($Dashboard -or $startBoth -or $All) {
    # Free port 3000 if occupied
    $existing = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    $dashDir = Join-Path $ROOT "dashboard"
    if (-not (Test-Path (Join-Path $dashDir "node_modules"))) {
        Write-Host "[dashboard] Installing dependencies..." -ForegroundColor Yellow
        Push-Location $dashDir
        $env:TEMP = "D:\npm-tmp"; $env:TMP = "D:\npm-tmp"
        npm install --silent 2>&1 | Out-Null
        Pop-Location
    }

    Write-Host "[dashboard] Starting Next.js on :3000..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-Command",
        "Set-Location '$dashDir'; `$env:TEMP='D:\npm-tmp'; `$env:TMP='D:\npm-tmp'; npm run dev"
    ) -WindowStyle Minimized
    Write-Host "  Started" -ForegroundColor DarkGreen
}

# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------
Write-Host ""
Write-Host "  Life Graph is running!" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:$API_PORT" -ForegroundColor White
Write-Host "  API Docs:     http://localhost:$API_PORT/docs" -ForegroundColor White
Write-Host "  Dashboard:    http://localhost:3000" -ForegroundColor White
Write-Host "  WebSocket:    ws://localhost:$API_PORT/ws" -ForegroundColor White
Write-Host ""
Write-Host '  Stop with:    .\stop.ps1' -ForegroundColor DarkGray
Write-Host '  Status:       .\status.ps1' -ForegroundColor DarkGray
Write-Host ""
