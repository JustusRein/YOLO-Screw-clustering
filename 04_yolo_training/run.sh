#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
SERVICE="yolo-trainer"
ACTION="train"
if (($#)) && [[ "$1" != --* ]]; then
  ACTION="$1"
  shift
fi

usage() {
  cat <<'EOF'
Usage: ./run.sh [train|predict|build] [--no-build]
  train      Prepare the synthetic dataset and train a YOLO model (default).
  predict    Run inference on images in input/predict/.
  build      Build the Docker image only.
  --no-build Reuse the existing Docker image.
EOF
}
BUILD=1
for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    --build-only) ACTION=build ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done
case "$ACTION" in
  train|predict|build) ;;
  *) echo "Unknown action: $ACTION" >&2; usage >&2; exit 2 ;;
esac

mkdir -p output input/predict
if [[ "$ACTION" != "build" ]]; then
  [[ -d ../03_image_generation/output ]] || {
    echo "Missing image dataset directory. Run stage 3 first." >&2
    exit 1
  }
fi
if (( BUILD )); then docker compose build "$SERVICE"; fi
if [[ "$ACTION" == "train" ]]; then
  docker compose run --rm "$SERVICE" python /workspace/scripts/train.py
elif [[ "$ACTION" == "predict" ]]; then
  [[ -f output/weights/best.pt ]] || {
    echo "Missing output/weights/best.pt. Train a model first." >&2
    exit 1
  }
  docker compose run --rm "$SERVICE" python /workspace/scripts/predict.py
fi
