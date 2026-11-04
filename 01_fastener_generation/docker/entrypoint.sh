#!/usr/bin/env bash
set -euo pipefail
mkdir -p /data/input /data/output
exec blender -b --factory-startup --python /workspace/generate_step_dataset.py
