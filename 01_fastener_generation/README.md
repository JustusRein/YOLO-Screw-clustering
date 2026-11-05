# Stage 1 – Fastener CAD generation

This stage uses FreeCAD and the FreeCAD Fasteners Workbench to generate labeled fastener CAD models from `input/fasteners.csv`.

## What it does

- Reads the fastener table.
- Creates supported screws, nuts, and washers using the configured standard identifier.
- Exports STL and STEP meshes and FreeCAD documents.
- Writes `generated_metadata.csv`, which is consumed by the Blender stage.

The generator currently supports the standards registered in `scripts/generate_fasteners.FCMacro`. The tracked CSV is the authoritative example of the expected input schema.

## Input CSV

Path: `input/fasteners.csv`

Required columns:

| Column | Purpose |
|---|---|
| `id` | Unique row/part identifier |
| `fastener_type` | Supported standard key, e.g. `ISO4762` |
| `diameter` | Diameter value accepted by the FreeCAD Fasteners object |

Other columns used by the generator or exported metadata include:

- `part_category` – `screw`, `nut`, or `washer`.
- `part_type` – descriptive part name used in output filenames.
- `length_mm` – required for screw types that have a length parameter.
- `screw_type`, `tool_size`, `thread_size`, `thread_pitch`, `screw_length` – class/part metadata fields.

Use the existing CSV as a working template. The current macro validates required columns and supported standard/category combinations. A standard must be present in `SUPPORTED_TYPES` in `scripts/generate_fasteners.FCMacro`.

## Run

From the repository root:

```bash
./01_fastener_generation/run.sh
```

Or from this directory:

```bash
./run.sh
```

The launcher builds the image and runs the `freecad-generator` Compose service. Other modes:

```bash
./run.sh --build-only
./run.sh --no-build
./run.sh --help
```

## Docker environment

| Variable | Default | Meaning |
|---|---|---|
| `INPUT_CSV` | `/data/input/fasteners.csv` | Input table |
| `OUTPUT_DIR` | `/data/output` | Output root |

FreeCAD and the Fasteners Workbench are installed in the image. The macro runs headlessly through Xvfb.

## Outputs

```text
output/
├── stl/                    # Target meshes used by Blender
├── step/                   # CAD exchange files
├── fcstd/                  # Native FreeCAD documents
├── generated_metadata.csv  # Model-to-class metadata for stage 3
└── generation_log.txt      # Generation log
```

Do not commit generated output. The repository `.gitignore` excludes each stage's `output/` directory.

## Troubleshooting

- **Unsupported fastener type:** add a supported Fasteners Workbench standard to `SUPPORTED_TYPES` and verify its category.
- **Unsupported diameter/length:** use values exposed by the installed Fasteners Workbench object, or inspect the macro's custom-length handling.
- **Stage 3 cannot find metadata:** confirm `output/generated_metadata.csv` exists and is non-empty after a successful run.
- **Workbench import failure:** rebuild the image so the Fasteners Workbench clone and FreeCAD environment are installed.
