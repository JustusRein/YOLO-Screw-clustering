$ErrorActionPreference = "Stop"

# ============================================================
# CONFIGURATION
# ============================================================

$SCRIPT_DIR = $PSScriptRoot
Set-Location $SCRIPT_DIR

$SERVICE = "yolo-trainer"
$ACTION = "train"
$BUILD = $true

# ============================================================
# ARGUMENTS
# ============================================================

if ($args.Count -gt 0 -and $args[0] -notlike "--*") {
    $ACTION = $args[0]
    $args = $args | Select-Object -Skip 1
}

foreach ($arg in $args) {
    switch ($arg) {
        "--no-build" {
            $BUILD = $false
        }
        "--build-only" {
            $ACTION = "build"
        }
        "-h" {
            Write-Host "Usage: .\run.ps1 [train|predict|build] [--no-build]"
            exit 0
        }
        "--help" {
            Write-Host "Usage: .\run.ps1 [train|predict|build] [--no-build]"
            exit 0
        }
        default {
            Write-Error "Unknown option: $arg"
            exit 2
        }
    }
}

if ($ACTION -notin @("train", "predict", "build")) {
    Write-Error "Unknown action: $ACTION"
    exit 2
}

# ============================================================
# DIRECTORIES
# ============================================================

New-Item -ItemType Directory -Force -Path "output" | Out-Null
New-Item -ItemType Directory -Force -Path "input/predict" | Out-Null

if ($ACTION -ne "build") {
    $DATASET_DIR = Join-Path $SCRIPT_DIR "..\03_image_generation\output"

    if (!(Test-Path $DATASET_DIR -PathType Container)) {
        Write-Error "Missing image dataset directory. Run stage 3 first."
        exit 1
    }
}

# ============================================================
# DOCKER COMPOSE
# ============================================================

function Invoke-DockerCompose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ComposeArgs
    )

    & docker compose @ComposeArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker Compose failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

# ============================================================
# BUILD
# ============================================================

if ($BUILD) {
    Write-Host "`n[yolo-training] Building Docker image..." -ForegroundColor Cyan

    Invoke-DockerCompose -ComposeArgs @(
        "build",
        $SERVICE
    )
}

# ============================================================
# TRAIN
# ============================================================

if ($ACTION -eq "train") {
    Write-Host "`n[yolo-training] Starting training..." -ForegroundColor Green

    Invoke-DockerCompose -ComposeArgs @(
        "run",
        "--rm",
        $SERVICE,
        "python",
        "/workspace/scripts/train.py"
    )
}

# ============================================================
# PREDICT
# ============================================================

elseif ($ACTION -eq "predict") {

    if (!(Test-Path "output/weights/best.pt")) {
        Write-Error "Missing output/weights/best.pt. Train a model first."
        exit 1
    }

    Write-Host "`n[yolo-training] Starting prediction..." -ForegroundColor Green

    Invoke-DockerCompose -ComposeArgs @(
        "run",
        "--rm",
        $SERVICE,
        "python",
        "/workspace/scripts/predict.py"
    )
}

Write-Host "`n[yolo-training] Finished." -ForegroundColor Green