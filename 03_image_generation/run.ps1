
[CmdletBinding()]
param(
    [switch]$BuildOnly,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$Service = "image-generator"
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
    Write-Host " SYNTHETIC IMAGE GENERATION" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan

    if (-not $BuildOnly) {
        $FastenerDir = Join-Path $ProjectDir "../01_fastener_generation/output/stl"
        $MetadataFile = Join-Path $ProjectDir "../01_fastener_generation/output/generated_metadata.csv"
        $DistractorDir = Join-Path $ProjectDir "../02_distractor_generation/output/stl"

        if (-not (Test-Path $FastenerDir -PathType Container)) {
            throw "Fastener STL-Verzeichnis fehlt. Bitte Projekt 1 ausführen."
        }

        if (-not (Test-Path $MetadataFile -PathType Leaf)) {
            throw "generated_metadata.csv fehlt. Bitte Projekt 1 ausführen."
        }

        if (-not (Test-Path $DistractorDir -PathType Container)) {
            throw "Distractor STL-Verzeichnis fehlt. Bitte Projekt 2 ausführen."
        }
    }

    New-Item -ItemType Directory -Force -Path "output" | Out-Null
    New-Item -ItemType Directory -Force -Path "input/backgrounds" | Out-Null

    if (-not $NoBuild) {
        Write-Host "`n[1/2] Building Blender Docker image..." -ForegroundColor Yellow

        Invoke-DockerCompose @(
            "build",
            "--progress",
            "plain",
            $Service
        )
    }

    if (-not $BuildOnly) {
        Write-Host "`n[2/2] Starting Blender rendering..." -ForegroundColor Yellow

        Invoke-DockerCompose @(
            "run",
            "--rm",
            "--no-TTY",
            $Service
        )
    }

    Write-Host "`nIMAGE GENERATION FINISHED" -ForegroundColor Green
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
