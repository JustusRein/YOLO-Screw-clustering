#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
SERVICE="distractor-generator"

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

mkdir -p output
if [[ ! -f input/distractors.csv ]]; then
  echo "ERROR: input/distractors.csv is missing." >&2
  exit 1
fi
if (( BUILD )); then docker compose build "$SERVICE"; fi
if (( RUN )); then docker compose run --rm "$SERVICE"; fi
