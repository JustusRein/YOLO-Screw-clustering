# Stage 4 – Dataset preparation, YOLO training, and prediction

This stage validates the synthetic Blender dataset, creates train/validation/test splits, trains an Ultralytics YOLO detector, and optionally performs inference on user-provided images.

## Input

The generated dataset is mounted read-only from:

```text
../03_image_generation/output/
```

The preparation script locates the generated `multi_object_dataset_*` directory and validates image/label pairs, image dimensions, annotation values, and dataset contents. It creates splits by scene so that images from one rendered scene do not leak across subsets.

Default split ratios are implemented in `scripts/prepare_dataset.py` (currently 80% train, 10% validation, 10% test).

## Run training

```bash
./04_yolo_training/run.sh
```

Or from this directory:

```bash
./run.sh
./run.sh train
```

The launcher builds the image, prepares the dataset, and starts training.

Build only:

```bash
./run.sh build
```

Reuse an existing image:

```bash
./run.sh train --no-build
```

## Prediction

Place images (`.png`, `.jpg`, `.jpeg`, or `.bmp`) in:

```text
input/predict/
```

Then run:

```bash
./run.sh predict
```

Prediction requires a trained model at `output/weights/best.pt`.

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `MODEL` | `yolo11n.pt` | Model name or initial weights |
| `EPOCHS` | `100` | Training epochs |
| `IMAGE_SIZE` | `1280` | Training/inference image size |
| `BATCH_SIZE` | `2` | Batch size |
| `WORKERS` | `2` | Data-loader workers |
| `LEARNING_RATE` | `0.001` | Initial learning rate |
| `PATIENCE` | `30` | Early-stopping patience |
| `RANDOM_SEED` | `42` | Training seed |
| `DEVICE` | `cpu` | Compute device |
| `CONFIDENCE` | `0.25` | Prediction confidence threshold |
| `IOU_THRESHOLD` | `0.45` | Prediction NMS IoU threshold |

Override values for a run:

```bash
EPOCHS=50 BATCH_SIZE=4 DEVICE=cpu ./run.sh train
```

## Outputs

```text
output/
├── datasets/       # Prepared YOLO datasets and reports
├── runs/           # Ultralytics training and evaluation runs
├── weights/
│   └── best.pt     # Stable copy of the best checkpoint
└── predictions/    # Timestamped inference results
```

## CPU and GPU

The default image installs CPU-only PyTorch to provide a predictable baseline. NVIDIA GPU training is not enabled automatically. It requires a CUDA-compatible PyTorch build, NVIDIA Container Toolkit, Docker GPU passthrough, and `DEVICE=0`. See `docs/INSTALLATION.md`.

## Troubleshooting

- **No source dataset:** complete stage 3 and verify it created a timestamped dataset directory.
- **No validation split:** increase the number of independently generated scenes and inspect the preparation report.
- **Out of memory:** reduce `BATCH_SIZE`, `IMAGE_SIZE`, or `WORKERS`.
- **Prediction weights missing:** run training first.
- **CUDA unavailable:** the default image is CPU-only; configure the CUDA build and GPU passthrough before selecting `DEVICE=0`.
