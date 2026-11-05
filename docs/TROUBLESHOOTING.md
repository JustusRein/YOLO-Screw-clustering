# Troubleshooting

## Docker command not found

Install Docker Engine or Docker Desktop and verify that `docker` and `docker compose` are available in the same shell used to run the scripts.

On Windows, use a WSL2 terminal and enable Docker Desktop integration for that distribution.

## Permission denied when running `run.sh`

Set executable permissions:

```bash
chmod +x run.sh 0*/run.sh
```

If the repository was extracted on a filesystem that does not preserve Unix permissions, run this command again after extraction.

## Stage 1 or 2 reports a missing CSV

Check that the tracked input CSV exists at the exact path:

- `01_fastener_generation/input/fasteners.csv`
- `02_distractor_generation/input/distractors.csv`

Check the CSV headers and values against the corresponding FreeCAD macro.

## Stage 3 reports missing STL files or metadata

Run stages 1 and 2 first. Stage 3 requires:

- `01_fastener_generation/output/stl/`
- `01_fastener_generation/output/generated_metadata.csv`
- `02_distractor_generation/output/stl/`

Check that stage 1 generated non-empty exports and that the metadata references the exported models.

## Blender exits with a rendering error

Inspect the full container output. Reduce `SCENE_COUNT`, render resolution, or `EEVEE_SAMPLES` to lower resource usage. Confirm that the Blender base image can access all mounted inputs. Background images are optional; place them in `03_image_generation/input/backgrounds/`.

## YOLO reports that no dataset or validation images exist

Run stage 3 and confirm that it produced a timestamped `multi_object_dataset_*` directory with `images/` and `labels/`. The training preparation script requires enough independent scenes to create a validation split. Review its dataset report and source labels.

## PyTorch runs on CPU even though the host has an NVIDIA GPU

The default Dockerfile deliberately installs CPU-only PyTorch. Follow the GPU setup section in `docs/INSTALLATION.md`, use a CUDA-compatible wheel, enable Docker GPU passthrough, rebuild the image, and verify CUDA availability inside the container before setting `DEVICE=0`.

## Prediction reports missing weights or input images

Train the model first so that `04_yolo_training/output/weights/best.pt` exists. Place supported image files (`.png`, `.jpg`, `.jpeg`, `.bmp`) in `04_yolo_training/input/predict/`, then run:

```bash
./04_yolo_training/run.sh predict
```

## Rebuild a stage after changing its Dockerfile

```bash
./04_yolo_training/run.sh
```

The stage launchers rebuild by default. If you intentionally want to use the previous image, pass `--no-build`.

## Inspect containers and images

```bash
docker compose -f 04_yolo_training/docker-compose.yml ps
docker image ls
docker system df
```

Compose commands should normally be run from the stage directory so relative volume paths resolve as expected.
