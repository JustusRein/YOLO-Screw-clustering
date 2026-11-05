# Installation and setup

## 1. Install Docker

### Linux

Install Docker Engine and the Docker Compose v2 plugin using the instructions for your distribution. Verify:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

If your Linux user is not in the `docker` group, use `sudo` for Docker commands or configure Docker group access according to Docker's security guidance.

### Windows 10/11

1. Install WSL2 and a Linux distribution.
2. Install Docker Desktop.
3. Enable the WSL2 backend and integration for the selected distribution in Docker Desktop.
4. Open the WSL2 terminal and verify `docker`, `docker compose`, and `docker run --rm hello-world`.
5. Clone the repository inside the WSL2 filesystem (for example, under `~/projects/`) rather than under `/mnt/c` for better filesystem performance.

The pipeline uses Bash launchers. Native PowerShell is not the execution environment for the containers; `run.ps1` is only a convenience wrapper that calls WSL2.

## 2. Get the repository

```bash
git clone https://github.com/JustusRein/YOLO-Screw-clustering.git
cd YOLO-Screw-clustering
chmod +x run.sh 0*/run.sh
```

## 3. Check input files

Confirm that the following files exist:

- `01_fastener_generation/input/fasteners.csv`
- `02_distractor_generation/input/distractors.csv`

Optional Blender background images can be placed in `03_image_generation/input/backgrounds/`. Prediction images can be placed in `04_yolo_training/input/predict/`.

## 4. Build and run

Run the entire pipeline:

```bash
./run.sh
```

Build images only:

```bash
./run.sh --build-only
```

Run an individual stage:

```bash
./01_fastener_generation/run.sh
```

Each stage stores generated artifacts in its local `output/` directory. Those directories are mounted into the containers and persist when containers exit.

## GPU configuration

The YOLO Dockerfile installs CPU-only PyTorch by default. This is deliberate: it is the portable baseline and does not assume that the host has a supported NVIDIA driver/runtime.

For NVIDIA GPU training, all of the following must be true:

- The host has a supported NVIDIA GPU and driver.
- Docker is configured with NVIDIA Container Toolkit / GPU support.
- The installed PyTorch wheel matches the host's CUDA/driver compatibility.
- The Compose service is configured for GPU access (for example, using the Compose `gpus` setting supported by the installed Docker Compose version).

Set `TORCH_INDEX_URL` to the official PyTorch wheel index appropriate for the CUDA version, and add GPU passthrough to `04_yolo_training/docker-compose.yml` for your Docker version. Then rebuild:

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cuXXX \
  ./04_yolo_training/run.sh build
```

Replace `cuXXX` with a currently supported PyTorch CUDA wheel index. Do not copy a CUDA index blindly: check the official PyTorch installation selector for the target host. Set `DEVICE=0` when running training after confirming that CUDA is visible inside the container.

## Rebuilding images

The stage launchers rebuild by default:

```bash
./03_image_generation/run.sh
```

Reuse the current image without rebuilding:

```bash
./03_image_generation/run.sh --no-build
```

To rebuild only:

```bash
./03_image_generation/run.sh --build-only
```

## Cleanup

Remove stopped containers and unused build cache carefully:

```bash
docker container prune
docker builder prune
```

These commands can remove resources used by other projects. They do not delete the host-mounted stage output folders. To remove generated datasets, delete the corresponding `output/` folders manually after backing up anything important.
