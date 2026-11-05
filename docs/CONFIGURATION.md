# Configuration reference

The defaults below are declared in the stage Compose files or Python scripts. Environment variables can override Compose defaults, for example:

```bash
SCENE_COUNT=200 RANDOM_SEED=123 ./03_image_generation/run.sh
EPOCHS=60 BATCH_SIZE=4 DEVICE=cpu ./04_yolo_training/run.sh
```

## Stage 1 – Fastener generation

| Variable | Default | Description |
|---|---|---|
| `INPUT_CSV` | `/data/input/fasteners.csv` | Fastener generation table |
| `OUTPUT_DIR` | `/data/output` | CAD and metadata output directory |

The CSV schema and filename-based metadata rules are described in the stage README and implemented in `scripts/metadata.py`.

## Stage 2 – Distractor generation

| Variable | Default | Description |
|---|---|---|
| `INPUT_CSV` | `/data/input/distractors.csv` | Distractor generation table |
| `OUTPUT_DIR` | `/data/output` | Export directory |
| `RANDOM_SEED` | `42` | Random seed |
| `EXPORT_STEP` | `1` | Also export STEP files |
| `EXPORT_FCSTD` | `0` | Also export FreeCAD documents |

## Stage 3 – Image generation

| Variable | Default | Description |
|---|---:|---|
| `SCENE_COUNT` | `1000` | Number of scenes |
| `TARGET_MIN` / `TARGET_MAX` | `1` / `5` | Target fasteners per positive scene |
| `DISTRACTOR_MIN` / `DISTRACTOR_MAX` | `3` / `10` | Distractors per scene |
| `NEGATIVE_SCENE_PROBABILITY` | `0.05` | Probability of a scene without target fasteners |
| `TABLE_SIZE` | `220` | Virtual workspace size in millimetres |
| `RES_X` / `RES_Y` | `1280` / `720` | Render resolution |
| `RESOLUTION_PERCENTAGE` | `100` | Blender render percentage |
| `EEVEE_SAMPLES` | `16` | Eevee render samples |
| `RANDOM_SEED` | `42` | Random seed |
| `CLASS_ATTRIBUTE` | `screw_type` | Metadata field used for class labels |

Additional path variables (`INPUT_DIR`, `METADATA_FILE`, `DISTRACTOR_DIR`, `BACKGROUND_DIR`, `OUTPUT_DIR`) are set to container paths in Compose. Do not change them unless you also update the corresponding volume mounts.

## Stage 4 – YOLO training and prediction

| Variable | Default | Description |
|---|---:|---|
| `MODEL` | `yolo11n.pt` | Ultralytics model/pretrained weights |
| `EPOCHS` | `100` | Training epochs |
| `IMAGE_SIZE` | `1280` | Training/inference image size |
| `BATCH_SIZE` | `2` | Training batch size |
| `WORKERS` | `2` | Data-loader workers |
| `LEARNING_RATE` | `0.001` | Initial learning rate |
| `PATIENCE` | `30` | Early-stopping patience |
| `RANDOM_SEED` | `42` | Training seed |
| `DEVICE` | `cpu` | `cpu`, `0`, or another Ultralytics device selector |
| `CONFIDENCE` | `0.25` | Prediction confidence threshold |
| `IOU_THRESHOLD` | `0.45` | Prediction NMS IoU threshold |

The default container installs CPU PyTorch. A CUDA-compatible PyTorch build and Docker GPU passthrough must be configured before using `DEVICE=0`.

## Root launcher options

| Option | Effect |
|---|---|
| `--skip-1` | Do not run fastener generation |
| `--skip-2` | Do not run distractor generation |
| `--skip-3` | Do not run image generation |
| `--skip-4` | Do not run training |
| `--build-only` | Build selected stage images without running |
| `--no-build` | Run selected stages using existing images |
