$ErrorActionPreference = "Stop"
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) { throw "WSL2 is required. Use a WSL2 terminal with Docker Desktop integration." }
$linuxPath = (wsl.exe wslpath -a "$PSScriptRoot").Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxPath) { throw "Could not convert the stage path to WSL." }
wsl.exe bash -lc "cd '$linuxPath' && chmod +x run.sh && ./run.sh"
if ($LASTEXITCODE -ne 0) { throw "Stage failed (exit code $LASTEXITCODE)." }
