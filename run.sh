#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RUN_1=1; RUN_2=1; RUN_3=1; RUN_4=1
BUILD_ONLY=0; NO_BUILD=0
usage() {
  cat <<'EOF'
YOLO Screw Clustering pipeline

Usage: ./run.sh [options]

By default, all four stages run sequentially:
  1. Fastener CAD generation
  2. Distractor CAD generation
  3. Synthetic Blender image generation
  4. YOLO dataset preparation and model training

Options:
  --skip-1          Skip fastener generation.
  --skip-2          Skip distractor generation.
  --skip-3          Skip image generation.
  --skip-4          Skip YOLO training.
  --build-only      Build all selected Docker images, but do not run stages.
  --no-build        Do not rebuild images; use existing local images.
  -h, --help        Show this help.

To resume from an existing stage, skip earlier stages. Required output
directories and metadata must already exist.
EOF
}
while (($#)); do
  case "$1" in
    --skip-1) RUN_1=0 ;;
    --skip-2) RUN_2=0 ;;
    --skip-3) RUN_3=0 ;;
    --skip-4) RUN_4=0 ;;
    --build-only) BUILD_ONLY=1 ;;
    --no-build) NO_BUILD=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

run_stage() {
  local label="$1" directory="$2"; shift 2
  echo
  echo "============================================================"
  echo " $label"
  echo "============================================================"
  if (( BUILD_ONLY )); then
    (cd "$ROOT_DIR/$directory" && ./run.sh --build-only)
  elif (( NO_BUILD )); then
    (cd "$ROOT_DIR/$directory" && ./run.sh --no-build "$@")
  else
    (cd "$ROOT_DIR/$directory" && ./run.sh "$@")
  fi
}

(( RUN_1 )) && run_stage "STAGE 1/4 - FASTENER GENERATION" "01_fastener_generation"
(( RUN_2 )) && run_stage "STAGE 2/4 - DISTRACTOR GENERATION" "02_distractor_generation"
(( RUN_3 )) && run_stage "STAGE 3/4 - SYNTHETIC IMAGE GENERATION" "03_image_generation"
(( RUN_4 )) && run_stage "STAGE 4/4 - YOLO TRAINING" "04_yolo_training"

echo
echo "Pipeline command sequence completed."
echo "Review the output/ directories of each stage for generated artifacts."
