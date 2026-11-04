#!/bin/bash

set -e

echo "===================================="
echo "FreeCAD Fastener Generator"
echo "===================================="

mkdir -p /data/output/step
mkdir -p /data/output/stl
mkdir -p /data/output/fcstd

echo "Starting FreeCAD macro..."

xvfb-run -a freecad \
    /app/scripts/generate_fasteners.FCMacro

echo "Generation completed."