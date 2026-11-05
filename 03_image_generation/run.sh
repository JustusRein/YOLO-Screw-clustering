#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
SERVICE="image-generator"

usage() {
  echo "Usage: ./run.sh [--build-only] [--no-build]"
}
BUILD=1
RUN=1
while (($#)); do
  case "$1" in
    --build-only) RUN=0 ;;
    --no-build) BUILD=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

mkdir -p output input/backgrounds
FASTENER_DIR="../01_fastener_generation/output/stl"
METADATA="../01_fastener_generation/output/generated_metadata.csv"
DISTRACTOR_DIR="../02_distractor_generation/output/stl"
[[ -d "$FASTENER_DIR" ]] || { echo "Missing fastener STL directory: $FASTENER_DIR. Run stage 1 first." >&2; exit 1; }
[[ -f "$METADATA" ]] || { echo "Missing fastener metadata: $METADATA. Run stage 1 first." >&2; exit 1; }
[[ -d "$DISTRACTOR_DIR" ]] || { echo "Missing distractor STL directory: $DISTRACTOR_DIR. Run stage 2 first." >&2; exit 1; }

if (( BUILD )); then docker compose build "$SERVICE"; fi
if (( RUN )); then docker compose run --rm "$SERVICE"; fi
