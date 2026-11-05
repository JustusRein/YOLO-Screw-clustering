# Stage 3 – Synthetic image generation

This stage uses headless Blender to render synthetic scenes containing labeled fasteners and unlabeled distractors. It also projects target-object bounding boxes into image coordinates and writes YOLO-format annotation files.

## Inputs

The Compose file mounts the following host directories:

| Host path | Container path | Purpose |
|---|---|---|
| `../01_fastener_generation/output/stl/` | `/data/input/stl/` | Labeled target meshes |
| `../01_fastener_generation/output/generated_metadata.csv` | `/data/input/generated_metadata.csv` | Target class metadata |
| `../02_distractor_generation/output/stl/` | `/data/input/distractors/` | Unlabeled distractor meshes |
| `input/backgrounds/` | `/data/input/backgrounds/` | Optional background images |

Run stages 1 and 2 before this stage. The launcher checks that required inputs exist.

## Scene generation

The Blender script randomizes scene composition, object placement/orientation, materials, camera and lighting. Fasteners are target objects and receive labels. Distractors are rendered without labels. Negative scenes can be generated with no target fasteners.

The default render resolution is 1280 × 720 (16:9), matching the configured reference camera resolution.

## Run

```bash
./03_image_generation/run.sh
```

Or from this directory:

```bash
./run.sh
```

Options:

```bash
./run.sh --build-only
./run.sh --no-build
./run.sh --help
```

## Configuration

The main settings are environment variables declared in `docker-compose.yml`:

| Variable | Default | Meaning |
|---|---:|---|
| `SCENE_COUNT` | `1000` | Number of scenes to render |
| `TARGET_MIN` / `TARGET_MAX` | `1` / `5` | Target fasteners per positive scene |
| `DISTRACTOR_MIN` / `DISTRACTOR_MAX` | `3` / `10` | Distractors per scene |
| `NEGATIVE_SCENE_PROBABILITY` | `0.05` | Probability of a negative scene |
| `TABLE_SIZE` | `220` | Virtual work surface size in mm |
| `RES_X` / `RES_Y` | `1280` / `720` | Image dimensions |
| `RESOLUTION_PERCENTAGE` | `100` | Blender render percentage |
| `EEVEE_SAMPLES` | `16` | Eevee samples |
| `RANDOM_SEED` | `42` | Random seed |
| `CLASS_ATTRIBUTE` | `screw_type` | Metadata field mapped to YOLO classes |

Example:

```bash
SCENE_COUNT=100 EEVEE_SAMPLES=8 ./run.sh
```

## Output

Each run creates a timestamped dataset directory under `output/`, typically:

```text
output/
└── multi_object_dataset_YYYYMMDD_HHMMSS/
    ├── images/
    ├── labels/
    ├── classes.txt
    ├── class_mapping.json
    ├── metadata.csv
    └── input_errors.csv
```

Each image has a corresponding `.txt` label file. Each annotation line follows:

```text
class_id x_center y_center width height
```

Coordinates and dimensions are normalized to the image size. Images without target objects have empty label files.

## Troubleshooting

- **Missing fastener metadata or STL directory:** run stage 1 and check its output.
- **Missing distractor STL directory:** run stage 2 and check its output.
- **Rendering is too slow or memory-intensive:** reduce `SCENE_COUNT`, resolution, or `EEVEE_SAMPLES`.
- **No useful target labels:** verify `CLASS_ATTRIBUTE` exists in the metadata and that the metadata-to-STL filenames match.
