
$ErrorActionPreference = "Stop"

Write-Host "===================================="
Write-Host "YOLO Screw Head Training"
Write-Host "===================================="

Write-Host ""
Write-Host "Building Docker image..."

docker compose build yolo-trainer

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}

Write-Host ""
Write-Host "Starting YOLO training..."

docker compose run --rm yolo-trainer

if ($LASTEXITCODE -ne 0) {
    throw "YOLO training failed."
}

Write-Host ""
Write-Host "===================================="
Write-Host "YOLO training completed."
Write-Host "===================================="
