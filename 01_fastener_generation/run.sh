
#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE="freecad-generator"

BUILD=1
RUN=1

usage() {
    cat <<'EOF'
Fastener Generator

Usage: ./run.sh [options]

Options:
  --build-only  Build the Docker image without running the generator.
  --no-build    Run using the already-built image.
  -h, --help    Show this help.
EOF
}

while (($#)); do
    case "$1" in
        --build-only)
            RUN=0
            ;;
        --no-build)
            BUILD=0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

echo "=================================================="
echo " FASTENER GENERATION"
echo "=================================================="

# Check required input
if (( RUN )); then
    if [[ ! -f input/fasteners.csv ]]; then
        echo "ERROR: input/fasteners.csv is missing." >&2
        exit 1
    fi
fi

# Create output directory
mkdir -p output

# Build image
if (( BUILD )); then
    echo ""
    echo "[1/2] Building Docker image..."
    docker compose build "$SERVICE"
fi

# Run generator
if (( RUN )); then
    echo ""
    echo "[2/2] Starting FreeCAD generator..."
    docker compose run --rm "$SERVICE"
fi

echo ""
echo "=================================================="
echo " FASTENER GENERATION FINISHED"
echo "=================================================="
