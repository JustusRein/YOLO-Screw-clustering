
#!/usr/bin/env bash
set -Eeuo pipefail

INPUT_CSV="${INPUT_CSV:-/data/input/distractors.csv}"

mkdir -p /data/output/stl /data/output/step /data/output/fcstd

if [[ ! -f "$INPUT_CSV" ]]; then
    echo "[distractor-generator] ERROR: CSV not found: $INPUT_CSV" >&2
    exit 1
fi

if [[ ! -f /app/scripts/generate_distractors.FCMacro ]]; then
    echo "[distractor-generator] ERROR: Macro not found." >&2
    exit 1
fi

echo "[distractor-generator] Starting FreeCAD macro..."

export PYTHONUNBUFFERED=1

exec /opt/conda/bin/freecadcmd /app/scripts/generate_distractors.FCMacro
