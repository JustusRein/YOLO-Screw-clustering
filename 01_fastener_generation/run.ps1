
[CmdletBinding()]
param(
    [switch]$BuildOnly,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$Service = "freecad-generator"
$LocationPushed = $false

function Invoke-DockerCompose {
    param([string[]]$ComposeArgs)

    & docker compose @ComposeArgs
    $code = $LASTEXITCODE

    if ($code -ne 0) {
        throw "Docker Compose fehlgeschlagen (Exit-Code $code)."
    }
}

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker wurde nicht gefunden. Bitte Docker Desktop starten."
    }

    Push-Location $ProjectDir
    $LocationPushed = $true

    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host " FASTENER GENERATION" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan

    if (-not $BuildOnly) {
        if (-not (Test-Path "input/fasteners.csv" -PathType Leaf)) {
            throw "input/fasteners.csv fehlt."
        }
    }

    New-Item -ItemType Directory -Force -Path "output" | Out-Null

    if (-not $NoBuild) {
        Write-Host "`n[1/2] Building Docker image..." -ForegroundColor Yellow

        Invoke-DockerCompose @(
            "build",
            "--progress",
            "plain",
            $Service
        )
    }

    if (-not $BuildOnly) {
        Write-Host "`n[2/2] Starting FreeCAD generator..." -ForegroundColor Yellow

        Invoke-DockerCompose @(
            "run",
            "--rm",
            "--no-TTY",
            $Service
        )
    }

    Write-Host "`nFASTENER GENERATION FINISHED" -ForegroundColor Green
}
catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    if ($LocationPushed) {
        Pop-Location
    }
}
