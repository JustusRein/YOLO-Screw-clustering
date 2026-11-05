# Architecture and data flow

## Design principles

- Each stage is independently buildable and runnable.
- Each stage owns its Docker image, Compose service, launcher, inputs, scripts, and outputs.
- The root launcher orchestrates stages in dependency order.
- Host-mounted output directories preserve generated data after containers are removed.
- Generated artifacts are excluded from Git to avoid committing large datasets and model weights.

## Stage responsibilities

### Stage 1 – Fastener generation

FreeCAD reads `input/fasteners.csv` and creates fastener CAD exports. The generator writes STL files and `generated_metadata.csv` under `output/`. Metadata is consumed by Blender to map each target STL model to its detection class.

### Stage 2 – Distractor generation

FreeCAD reads `input/distractors.csv` and exports distractor objects. These objects are scene content, not target detection classes.

### Stage 3 – Synthetic image generation

Blender reads:

- Stage 1 STL files from `01_fastener_generation/output/stl/`.
- Stage 1 metadata from `01_fastener_generation/output/generated_metadata.csv`.
- Stage 2 STL files from `02_distractor_generation/output/stl/`.
- Optional background images from `input/backgrounds/`.

It creates timestamped datasets containing images, YOLO labels, class mappings, scene metadata, and error reports. Fasteners receive labels; distractors are rendered without labels. Negative scenes may contain no target fasteners.

### Stage 4 – Dataset preparation and YOLO training

The training container reads the generated Blender dataset, validates the source images and labels, creates train/validation/test splits, writes a YOLO dataset configuration, and starts Ultralytics training. The best checkpoint is copied to `output/weights/best.pt`.

Prediction is a separate mode in the same image. Input images are read from `input/predict/`; prediction artifacts are written under `output/predictions/`.

## Execution and dependencies

The root `run.sh` executes the stages sequentially:

1. Fastener generation
2. Distractor generation
3. Image generation
4. Dataset preparation and training

Stages 1 and 2 can be generated independently, but both must be complete before stage 3. Stage 3 must produce a dataset before stage 4 can train.

Use `--skip-N` only when the skipped stage's outputs already exist and are valid.

## Docker volume strategy

Input data is mounted read-only where possible. Scripts are mounted read-only in Blender and YOLO stages. Output directories are mounted read-write from the host. This keeps the container image disposable while preserving generated files.

## Reproducibility

The CAD and Blender generators expose random seeds. YOLO training also receives a random seed. Preserve the CSV inputs, configuration values, metadata, dataset report, and training run directory when comparing experiments. Exact reproducibility can still depend on software versions, hardware, and GPU kernels.
