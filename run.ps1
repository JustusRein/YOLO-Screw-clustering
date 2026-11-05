$ErrorActionPreference = "Stop"
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL2 is required. Install WSL2 and Docker Desktop with WSL integration."
}
$linuxPath = (wsl.exe wslpath -a "$PSScriptRoot").Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxPath) {
    throw "Could not convert the repository path to a WSL path."
}
wsl.exe bash -lc "cd '$linuxPath' && chmod +x ./run.sh ./0*/run.sh && ./run.sh"
if ($LASTEXITCODE -ne 0) {
    throw "YOLO Screw Clustering pipeline failed (exit code $LASTEXITCODE)."
}
