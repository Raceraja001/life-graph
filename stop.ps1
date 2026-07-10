<#
.SYNOPSIS
    Stop the Life Graph application.
.EXAMPLE
    .\stop.ps1              # Stop API + dashboard (keeps Postgres/Redis)
    .\stop.ps1 -All         # Stop everything including Docker
    .\stop.ps1 -Backend     # Stop only backend API
    .\stop.ps1 -Dashboard   # Stop only dashboard
    .\stop.ps1 -Infra       # Stop only Docker (Postgres + Redis)
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
Write-Host "  Life Graph - Stopping..." -ForegroundColor Cyan
Write-Host ""

# Default: stop backend + dashboard
$stopBoth = -not $Backend -and -not $Dashboard -and -not $Infra -and -not $All

# ----------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------
if ($Dashboard -or $stopBoth -or $All) {
    Write-Host "[dashboard] Stopping..." -ForegroundColor Yellow
    $found = $false
    Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Killing $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor DarkGray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }
    # Kill orphaned node processes from Next.js
    if ($found) {
        Start-Sleep -Seconds 1
        Get-Process -Name "node" -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
                if ($cmd -match "next|turbopack|dashboard") {
                    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                }
            } catch {}
        }
    }
    if ($found) { Write-Host "  Stopped" -ForegroundColor DarkGreen }
    else { Write-Host "  Not running" -ForegroundColor DarkGray }
}

# ----------------------------------------------------------------
# Backend API
# ----------------------------------------------------------------
if ($Backend -or $stopBoth -or $All) {
    Write-Host "[backend] Stopping..." -ForegroundColor Yellow
    $found = $false

    # Kill process on API port (skip Docker — we don't touch it)
    Get-NetTCPConnection -LocalPort $API_PORT -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -ne "com.docker.backend") {
            Write-Host "  Killing $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor DarkGray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }

    # Kill any local uvicorn processes
    Get-Process -Name "python*" -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmd -match "uvicorn.*life_graph") {
                Write-Host "  Killing uvicorn (PID $($_.Id))" -ForegroundColor DarkGray
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                $found = $true
            }
        } catch {}
    }

    if ($found) { Write-Host "  Stopped" -ForegroundColor DarkGreen }
    else { Write-Host "  Not running" -ForegroundColor DarkGray }
}

# ----------------------------------------------------------------
# Infrastructure (Docker: Postgres + Redis)
# ----------------------------------------------------------------
if ($Infra -or $All) {
    Write-Host "[infra] Stopping Docker services..." -ForegroundColor Yellow
    Push-Location $ROOT

    $job = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        docker compose down 2>&1
    } -ArgumentList $ROOT

    $done = Wait-Job $job -Timeout 60
    if ($done) {
        Receive-Job $job | ForEach-Object {
            if ($_ -match "Removed|Stopped") { Write-Host "  $_" -ForegroundColor DarkGray }
        }
        Write-Host "  Stopped" -ForegroundColor DarkGreen
    } else {
        Stop-Job $job
        Write-Host "  Docker slow, force killing..." -ForegroundColor Yellow
        $job2 = Start-Job { docker kill life_graph_db life_graph_redis 2>&1 }
        Wait-Job $job2 -Timeout 15 | Out-Null
        Remove-Job $job2 -Force -ErrorAction SilentlyContinue
        Write-Host "  Force killed" -ForegroundColor DarkGreen
    }
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host ""
Write-Host "  Life Graph stopped." -ForegroundColor Green
Write-Host ""
Write-Host '  Start with: .\start.ps1' -ForegroundColor DarkGray
Write-Host ""
