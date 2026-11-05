
[CmdletBinding()]
param(
    [switch]$Skip1,
    [switch]$Skip2,
    [switch]$Skip3,
    [switch]$Skip4,

    [switch]$BuildOnly,
    [switch]$NoBuild,

    [ValidateSet("train", "predict")]
    [string]$Action = "train"
)

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot

# ============================================================
# CONFIGURATION
# ============================================================

if ($BuildOnly -and $NoBuild) {
    throw "-BuildOnly und -NoBuild können nicht gleichzeitig verwendet werden."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker wurde nicht gefunden. Bitte Docker Desktop starten."
}

# ============================================================
# HELPER
# ============================================================

function Invoke-Stage {
    param(
        [Parameter(Mandatory)]
        [string]$Title,

        [Parameter(Mandatory)]
        [string]$Directory,

        [string[]]$Arguments = @()
    )

    $StageDir = Join-Path $RootDir $Directory
    $ScriptPath = Join-Path $StageDir "run.ps1"

    if (-not (Test-Path $ScriptPath -PathType Leaf)) {
        throw "PowerShell-Skript nicht gefunden: $ScriptPath"
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    Push-Location $StageDir

    try {
        Write-Host "`nStarting: $Directory" -ForegroundColor Yellow

        & $ScriptPath @Arguments

        if (-not $?) {
            throw "Stage fehlgeschlagen: $Directory"
        }

        Write-Host "`nCompleted: $Directory" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# ============================================================
# STAGE ARGUMENTS
# ============================================================

$StageArguments = @()

if ($BuildOnly) {
    $StageArguments = @("-BuildOnly")
}
elseif ($NoBuild) {
    $StageArguments = @("-NoBuild")
}

# ============================================================
# PIPELINE
# ============================================================

try {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "          YOLO SCREW CLUSTERING PIPELINE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green

    Write-Host "`nRepository: $RootDir"
    Write-Host "Action: $Action"
    Write-Host "`nDocker output will be displayed directly in PowerShell."

    # --------------------------------------------------------
    # STAGE 1
    # --------------------------------------------------------

    if (-not $Skip1) {
        Invoke-Stage `
            -Title "STAGE 1/4 - FASTENER GENERATION" `
            -Directory "01_fastener_generation" `
            -Arguments $StageArguments
    }

    # --------------------------------------------------------
    # STAGE 2
    # --------------------------------------------------------

    if (-not $Skip2) {
        Invoke-Stage `
            -Title "STAGE 2/4 - DISTRACTOR GENERATION" `
            -Directory "02_distractor_generation" `
            -Arguments $StageArguments
    }

    # --------------------------------------------------------
    # STAGE 3
    # --------------------------------------------------------

    if (-not $Skip3) {
        if (-not $BuildOnly) {
            $FastenerDir = Join-Path $RootDir "01_fastener_generation/output/stl"
            $MetadataFile = Join-Path $RootDir "01_fastener_generation/output/generated_metadata.csv"
            $DistractorDir = Join-Path $RootDir "02_distractor_generation/output/stl"

            if (-not (Test-Path $FastenerDir -PathType Container)) {
                throw "Fastener STL files fehlen. Projekt 1 ausführen."
            }

            if (-not (Test-Path $MetadataFile -PathType Leaf)) {
                throw "Fastener metadata fehlt. Projekt 1 ausführen."
            }

            if (-not (Test-Path $DistractorDir -PathType Container)) {
                throw "Distractor STL files fehlen. Projekt 2 ausführen."
            }
        }

        Invoke-Stage `
            -Title "STAGE 3/4 - SYNTHETIC IMAGE GENERATION" `
            -Directory "03_image_generation" `
            -Arguments $StageArguments
    }

    # --------------------------------------------------------
    # STAGE 4
    # --------------------------------------------------------

    if (-not $Skip4) {
        $Stage4Arguments = @()

        if ($BuildOnly) {
            $Stage4Arguments = @("build")
        }
        elseif ($NoBuild) {
            $Stage4Arguments = @($Action, "--no-build")
        }
        else {
            $Stage4Arguments = @($Action)
        }

        Invoke-Stage `
            -Title "STAGE 4/4 - YOLO $($Action.ToUpperInvariant())" `
            -Directory "04_yolo_training" `
            -Arguments $Stage4Arguments
    }

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " PIPELINE FINISHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green

    Write-Host "`nCheck the output directories for generated files."
}
catch {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " PIPELINE FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red

    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red

    exit 1
}
