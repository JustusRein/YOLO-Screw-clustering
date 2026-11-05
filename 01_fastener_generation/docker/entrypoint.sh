
#!/usr/bin/env bash
set -Eeuo pipefail

echo "[fastener-generator] Starting FreeCAD macro..."

INPUT_CSV="${INPUT_CSV:-/data/input/fasteners.csv}"

if [[ ! -f "$INPUT_CSV" ]]; then
    echo "[fastener-generator] ERROR: CSV not found: $INPUT_CSV" >&2
    exit 1
fi

if [[ ! -f /app/scripts/generate_fasteners.FCMacro ]]; then
    echo "[fastener-generator] ERROR: Macro not found." >&2
    exit 1
fi

mkdir -p /data/output/stl /data/output/step /data/output/fcstd

export PYTHONUNBUFFERED=1

exec /opt/conda/bin/freecadcmd /app/scripts/generate_fasteners.FCMacro
