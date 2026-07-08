<#
.SYNOPSIS
    Stop the Life Graph application (backend + dashboard).

.DESCRIPTION
    1. Stops the Next.js dashboard dev server
    2. Stops Docker containers (API, worker, Postgres, Redis, MinIO, MCP)

.EXAMPLE
    .\stop.ps1              # Stop everything
    .\stop.ps1 -Backend     # Stop only backend (Docker)
    .\stop.ps1 -Dashboard   # Stop only dashboard (Next.js)
    .\stop.ps1 -Destroy     # Stop everything + remove volumes (data wipe!)
#>
param(
    [switch]$Backend,
    [switch]$Dashboard,
    [switch]$Destroy   # Also remove Docker volumes (data loss!)
)

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Life Graph — Stopping..." -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor DarkCyan
Write-Host ""

# If neither flag is set, stop both
$stopBoth = -not $Backend -and -not $Dashboard

# ── Dashboard (Next.js) ──────────────────────────────────
if ($Dashboard -or $stopBoth) {
    Write-Host "[1/2] Stopping dashboard..." -ForegroundColor Yellow

    # Kill any Next.js dev server on port 3000
    $procs = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | ForEach-Object {
            $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Killing $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor DarkGray
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "  Dashboard stopped" -ForegroundColor DarkGreen
    } else {
        Write-Host "  Dashboard not running" -ForegroundColor DarkGray
    }

    # Also kill any orphaned node processes from npm run dev
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -eq "" -and $_.Path -match "node"
    } | ForEach-Object {
        # Check if it's our dashboard process
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            if ($cmdLine -match "next|dashboard") {
                Write-Host "  Killing orphan node (PID $($_.Id))" -ForegroundColor DarkGray
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
}

# ── Backend (Docker Compose) ─────────────────────────────
if ($Backend -or $stopBoth) {
    Write-Host "[2/2] Stopping Docker backend..." -ForegroundColor Yellow

    Push-Location $ROOT

    if ($Destroy) {
        Write-Host "  ⚠️  Destroying containers AND volumes (data will be lost)..." -ForegroundColor Red
        docker compose down -v 2>&1 | ForEach-Object {
            if ($_ -match "Removed|Stopped") { Write-Host "  $_" -ForegroundColor DarkGray }
        }
    } else {
        docker compose down 2>&1 | ForEach-Object {
            if ($_ -match "Removed|Stopped") { Write-Host "  $_" -ForegroundColor DarkGray }
        }
    }

    Write-Host "  Backend stopped" -ForegroundColor DarkGreen
    Pop-Location
}

# ── Summary ──────────────────────────────────────────────
Write-Host ""
Write-Host "  ✅ Life Graph stopped." -ForegroundColor Green
if ($Destroy) {
    Write-Host "  ⚠️  Volumes destroyed — data wiped." -ForegroundColor Red
}
Write-Host ""
Write-Host '  Start again with: .\start.ps1' -ForegroundColor DarkGray
Write-Host ""
