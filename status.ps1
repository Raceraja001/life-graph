<#
.SYNOPSIS
    Check status of all Life Graph services.
#>

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "  Life Graph - Status" -ForegroundColor Cyan
Write-Host ""

$services = @(
    @{ Name = "Backend API";  Port = 8000; Url = "http://localhost:8000/health" },
    @{ Name = "Dashboard";    Port = 3000; Url = "http://localhost:3000" },
    @{ Name = "PostgreSQL";   Port = 5432; Url = $null },
    @{ Name = "Redis";        Port = 6379; Url = $null },
    @{ Name = "MCP Server";   Port = 8001; Url = $null },
    @{ Name = "MinIO";        Port = 9001; Url = $null }
)

foreach ($svc in $services) {
    $listening = Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        $status = "RUNNING"
        $color = "Green"

        if ($svc.Url) {
            try {
                $r = Invoke-WebRequest -Uri $svc.Url -UseBasicParsing -TimeoutSec 2
                if ($r.StatusCode -eq 200) { $status = "HEALTHY" }
            } catch {
                $status = "LISTENING (unhealthy)"
                $color = "Yellow"
            }
        }
    } else {
        $status = "STOPPED"
        $color = "Red"
    }

    $label = $svc.Name.PadRight(14)
    $port = ":$($svc.Port)".PadRight(6)
    Write-Host "  $label $port  $status" -ForegroundColor $color
}

# DB migration
Write-Host ""
try {
    Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
    $rev = python -m alembic current 2>&1 | Select-String "^\d+" | ForEach-Object { $_.Matches[0].Value }
    Write-Host "  DB Migration: $rev" -ForegroundColor DarkGreen
    Pop-Location
} catch {
    Write-Host "  DB Migration: unknown" -ForegroundColor DarkGray
}

Write-Host ""
