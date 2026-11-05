# Stage 2 – Distractor CAD generation

This stage uses FreeCAD to create unlabeled mechanical objects that add visual clutter to synthetic scenes. Distractors are intentionally not assigned target YOLO classes.

## Input CSV

Path: `input/distractors.csv`

The supplied CSV defines the schema:

| Column | Purpose |
|---|---|
| `id` | Unique object identifier |
| `part_type` | Procedural geometry type |
| `variants` | Number of generated variations |
| `outer_diameter_mm` | Optional outer diameter |
| `inner_diameter_mm` | Optional inner diameter |
| `length_mm` | Optional length |
| `width_mm` | Optional width |
| `height_mm` | Optional height |
| `thickness_mm` | Optional thickness |
| `teeth` | Optional gear/tooth count |
| `variation_percent` | Random dimensional variation |

Not every parameter applies to every `part_type`. Follow the existing input rows and the validation/geometry logic in `scripts/generate_distractors.FCMacro` when adding new entries.

## Run

```bash
./02_distractor_generation/run.sh
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

## Docker environment

| Variable | Default | Meaning |
|---|---|---|
| `INPUT_CSV` | `/data/input/distractors.csv` | Input table |
| `OUTPUT_DIR` | `/data/output` | Output root |
| `RANDOM_SEED` | `42` | Random seed |
| `EXPORT_STEP` | `1` | Export STEP files in addition to STL |
| `EXPORT_FCSTD` | `0` | Export native FreeCAD documents |

## Outputs

```text
output/
├── stl/       # Distractor meshes consumed by stage 3
├── step/      # Optional STEP exports
└── fcstd/     # Optional native FreeCAD documents
```

## Troubleshooting

- **Missing CSV:** verify `input/distractors.csv` exists and is mounted.
- **No STL output:** inspect the FreeCAD log in the container output and verify `part_type` values are supported by the macro.
- **Stage 3 cannot find distractors:** run this stage first and confirm that `output/stl/` contains STL files.
