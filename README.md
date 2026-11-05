# YOLO Screw Clustering

A Docker-based, four-stage pipeline for creating synthetic training data and training YOLO object-detection models for screws, nuts, and other fasteners.

The pipeline combines procedural CAD generation in FreeCAD, synthetic scene rendering in Blender, automatic YOLO annotations, dataset validation/splitting, and model training with Ultralytics YOLO.

## Pipeline at a glance

| Stage | Directory | Container/service | Purpose |
|---|---|---|---|
| 1 | `01_fastener_generation/` | `freecad-generator` | Generate labeled fastener CAD models and metadata |
| 2 | `02_distractor_generation/` | `distractor-generator` | Generate unlabeled distractor CAD models |
| 3 | `03_image_generation/` | `image-generator` | Render synthetic images and YOLO labels |
| 4 | `04_yolo_training/` | `yolo-trainer` | Prepare the dataset, train YOLO, and optionally run prediction |

Each stage has its own `Dockerfile`, `docker-compose.yml`, and `run.sh`. The repository-level `run.sh` runs the complete pipeline sequentially.

```text
Fastener CSV                  Distractor CSV
     |                              |
     v                              v
+----------------------+   +----------------------+
| 1. Fastener          |   | 2. Distractor        |
|    generation       |   |    generation        |
| FreeCAD              |   | FreeCAD              |
+----------+-----------+   +-----------+----------+
           |                           |
           | labeled STL + metadata    | unlabeled STL
           +-------------+-------------+
                         |
                         v
              +----------------------+
              | 3. Image generation  |
              | Blender             |
              | RGB images + labels |
              +----------+-----------+
                         |
                         v
              +----------------------+
              | 4. YOLO training     |
              | Ultralytics/PyTorch  |
              | dataset + best.pt   |
              +----------------------+
```

## Requirements

- Docker Engine with the Docker Compose v2 plugin, or Docker Desktop.
- Linux, or Windows 10/11 with WSL2 and Docker Desktop WSL integration.
- Internet access for the initial image builds and pretrained model download.
- Enough disk space for CAD exports, rendered images, datasets, and model checkpoints.
- Recommended: 16 GB RAM or more for larger rendering/training runs. Actual requirements depend on scene count, image size, and batch size.

The default YOLO image installs CPU-only PyTorch. See [GPU configuration](docs/INSTALLATION.md#gpu-configuration) before changing this for an NVIDIA host.

## Quick start (Linux)

```bash
git clone https://github.com/JustusRein/YOLO-Screw-clustering.git
cd YOLO-Screw-clustering
chmod +x run.sh 0*/run.sh
./run.sh
```

The first run builds all four images and executes all four stages in order. Docker images are reused only when you explicitly pass `--no-build`; otherwise each stage is rebuilt before it runs.

## Quick start (Windows)

Use a WSL2 Linux distribution with Docker Desktop integration enabled. Clone the repository inside the WSL filesystem (recommended for performance), then run the Linux commands above from the WSL terminal.

A convenience PowerShell launcher is also provided:

```powershell
.\run.ps1
```

It delegates execution to WSL2. The individual stages are Bash scripts; run them from WSL2 rather than native PowerShell.

## Run individual stages

Run a stage from the repository root:

```bash
./01_fastener_generation/run.sh
./02_distractor_generation/run.sh
./03_image_generation/run.sh
./04_yolo_training/run.sh
```

The scripts build their Docker image and run the associated service. To build without running:

```bash
./01_fastener_generation/run.sh --build-only
```

To reuse an already-built image:

```bash
./03_image_generation/run.sh --no-build
```

YOLO training supports training, prediction, and build-only modes:

```bash
./04_yolo_training/run.sh train
./04_yolo_training/run.sh predict
./04_yolo_training/run.sh build
```

Prediction images must be placed in `04_yolo_training/input/predict/`. A trained model must exist at `04_yolo_training/output/weights/best.pt`.

## Run the complete pipeline

```bash
./run.sh
```

Useful options:

```bash
./run.sh --skip-1 --skip-2   # Reuse existing CAD outputs; render and train
./run.sh --skip-4            # Generate the dataset but do not train
./run.sh --skip-1 --skip-2 --skip-3
./run.sh --build-only        # Build all images without executing stages
./run.sh --no-build          # Run all stages with existing images
./run.sh --help
```

Skipped stages are not generated automatically. Their expected output files/directories must already exist.

## Inputs and outputs

| Stage | Tracked inputs | Generated outputs |
|---|---|---|
| 1 | `01_fastener_generation/input/fasteners.csv` and CAD/source settings | `01_fastener_generation/output/` |
| 2 | `02_distractor_generation/input/distractors.csv` | `02_distractor_generation/output/` |
| 3 | Stage 1 STL + `generated_metadata.csv`, stage 2 STL, optional backgrounds in `03_image_generation/input/backgrounds/` | Timestamped dataset under `03_image_generation/output/` |
| 4 | Stage 3 dataset, optional images in `04_yolo_training/input/predict/` | Prepared datasets, training runs, weights, predictions under `04_yolo_training/output/` |

Generated data is intentionally excluded from Git by `.gitignore`. Keep large datasets and model weights outside normal Git history (for example, use a suitable artifact store or Git LFS if versioning them is required).

## Configuration

Runtime settings are defined in each stage's `docker-compose.yml` and can be overridden with environment variables. Examples:

```bash
SCENE_COUNT=250 DEVICE=cpu EPOCHS=50 ./run.sh
```

See each stage README and [configuration reference](docs/CONFIGURATION.md) for details.

## Documentation

- [Installation and setup](docs/INSTALLATION.md)
- [Architecture and data flow](docs/ARCHITECTURE.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Stage 1 – Fastener generation](01_fastener_generation/README.md)
- [Stage 2 – Distractor generation](02_distractor_generation/README.md)
- [Stage 3 – Image generation](03_image_generation/README.md)
- [Stage 4 – YOLO training and prediction](04_yolo_training/README.md)

## Important notes

- Stage 1 uses the filename/CSV metadata logic implemented in `scripts/metadata.py`; it does not infer every semantic fastener property from CAD geometry.
- Stage 3 labels target fasteners. Distractors are deliberately rendered without target labels.
- Dataset splitting is performed by the preparation script. Review the generated dataset report before relying on model metrics.
- The default training device is CPU. Configure a compatible PyTorch CUDA image and Docker GPU passthrough before setting `DEVICE=0`.
- The container builds and execution are separate from a functional validation of generated CAD/render/training results. Always inspect the generated outputs and logs for your dataset.

## License and attribution

See the repository license, if present, and the licenses of the upstream software and Docker base images. FreeCAD, Blender, PyTorch, and Ultralytics are separate third-party projects.

**Author:** Justus Rein  
**Repository:** [JustusRein/YOLO-Screw-clustering](https://github.com/JustusRein/YOLO-Screw-clustering)
