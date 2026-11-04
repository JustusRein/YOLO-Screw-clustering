#!/bin/bash

set -e

echo "=========================================="
echo "FreeCAD Distractor Generator"
echo "=========================================="

mkdir -p /data/output/stl
mkdir -p /data/output/step
mkdir -p /data/output/fcstd

echo ""
echo "Input CSV:  /data/input/distractors.csv"
echo "Output:     /data/output"
echo ""

if [ ! -f /data/input/distractors.csv ]; then
    echo "ERROR: distractors.csv not found!"
    exit 1
fi

echo "Starting FreeCAD macro..."

xvfb-run -a freecad \
    /app/scripts/generate_distractors.FCMacro

echo ""
echo "=========================================="
echo "Distractor generation finished"
echo "=========================================="