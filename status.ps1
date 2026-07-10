<#
.SYNOPSIS
    Check status of all Life Graph services.
#>

$ErrorActionPreference = "Continue"
$API_PORT = 8080

Write-Host ""
Write-Host "  Life Graph - Status" -ForegroundColor Cyan
Write-Host ""

$services = @(
    @{ Name = "Backend API";  Port = $API_PORT; Health = "http://localhost:$API_PORT/health" },
    @{ Name = "Dashboard";    Port = 3000; Health = "http://localhost:3000" },
    @{ Name = "PostgreSQL";   Port = 5432; Health = $null },
    @{ Name = "Redis";        Port = 6379; Health = $null },
    @{ Name = "MCP Server";   Port = 8001; Health = $null },
    @{ Name = "MinIO";        Port = 9001; Health = $null }
)

foreach ($svc in $services) {
    $conn = Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $via = if ($proc.ProcessName -eq "com.docker.backend") { "(docker)" } else { "(local)" }
        $status = "RUNNING $via"
        $color = "Green"

        if ($svc.Health) {
            try {
                $r = Invoke-WebRequest -Uri $svc.Health -UseBasicParsing -TimeoutSec 3
                if ($r.StatusCode -eq 200) { $status = "HEALTHY $via" }
            } catch {
                $status = "UNHEALTHY $via"
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
    if ($rev) { Write-Host "  DB migration: $rev" -ForegroundColor DarkGreen }
    else { Write-Host "  DB migration: unknown" -ForegroundColor DarkGray }
    Pop-Location
} catch {
    Write-Host "  DB migration: error" -ForegroundColor Red
}

# Endpoint count
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$API_PORT/openapi.json" -UseBasicParsing -TimeoutSec 3
    $count = ($r.Content | ConvertFrom-Json).paths.PSObject.Properties.Count
    Write-Host "  API endpoints: $count" -ForegroundColor DarkGreen
} catch {}

Write-Host ""
