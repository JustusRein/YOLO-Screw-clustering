
$ErrorActionPreference = "Stop"

Write-Host "===================================="
Write-Host "YOLO Screw Image Generation"
Write-Host "===================================="

docker compose build image-generator

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}

docker compose run --rm image-generator

if ($LASTEXITCODE -ne 0) {
    throw "Blender image generation failed."
}

Write-Host "===================================="
Write-Host "Image generation completed."
Write-Host "===================================="
