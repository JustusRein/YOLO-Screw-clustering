
from __future__ import annotations

import os
import shutil
import time

from pathlib import Path
from datetime import datetime

from ultralytics import YOLO

from prepare_dataset import prepare_dataset


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_DIR = Path(os.environ.get(
    "OUTPUT_DIR",
    "/workspace/output"
))

MODEL = os.environ.get(
    "MODEL",
    "yolo11n.pt"
)

EPOCHS = int(os.environ.get(
    "EPOCHS",
    "100"
))

IMAGE_SIZE = int(os.environ.get(
    "IMAGE_SIZE",
    "1280"
))

BATCH_SIZE = int(os.environ.get(
    "BATCH_SIZE",
    "2"
))

WORKERS = int(os.environ.get(
    "WORKERS",
    "2"
))

LEARNING_RATE = float(os.environ.get(
    "LEARNING_RATE",
    "0.001"
))

PATIENCE = int(os.environ.get(
    "PATIENCE",
    "30"
))

DEVICE = os.environ.get(
    "DEVICE",
    "cpu"
)

RANDOM_SEED = int(os.environ.get(
    "RANDOM_SEED",
    "42"
))

# Preserve image aspect ratio during training.
RECTANGULAR_TRAINING = os.environ.get(
    "RECTANGULAR_TRAINING",
    "true"
).lower() in ("true", "1", "yes", "on")

# Expected Intel RealSense D405 resolution.
EXPECTED_WIDTH = int(os.environ.get(
    "EXPECTED_WIDTH",
    "1280"
))

EXPECTED_HEIGHT = int(os.environ.get(
    "EXPECTED_HEIGHT",
    "720"
))


# ============================================================
# LOGGING
# ============================================================

def log(message):

    print(
        f"[YOLO TRAINING] {message}",
        flush=True
    )


def format_time(seconds):

    if seconds < 60:
        return f"{seconds:.1f} seconds"

    minutes = int(seconds // 60)
    remaining = seconds % 60

    return f"{minutes} min {remaining:.1f} sec"


# ============================================================
# HELPERS
# ============================================================

def count_images(directory):

    if not directory.exists():
        return 0

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp"
    }

    return sum(
        1
        for path in directory.rglob("*")
        if path.suffix.lower() in extensions
    )


# ============================================================
# MAIN
# ============================================================

def main():

    total_start = time.perf_counter()

    log("========================================")
    log("STARTING YOLO TRAINING")
    log("========================================")

    log(f"Model: {MODEL}")
    log(f"Epochs: {EPOCHS}")
    log(f"Image size: {IMAGE_SIZE}")
    log(f"Expected camera resolution: {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
    log(f"Rectangular training: {RECTANGULAR_TRAINING}")
    log(f"Batch size: {BATCH_SIZE}")
    log(f"Workers: {WORKERS}")
    log(f"Learning rate: {LEARNING_RATE}")
    log(f"Patience: {PATIENCE}")
    log(f"Device: {DEVICE}")
    log(f"Random seed: {RANDOM_SEED}")

    # --------------------------------------------------------
    # 1. PREPARE DATASET
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log("----------------------------------------")
    log("STEP 1: PREPARING DATASET")
    log("----------------------------------------")

    (
        dataset_dir,
        dataset_yaml,
        has_val,
        has_test
    ) = prepare_dataset()

    dataset_dir = Path(dataset_dir)
    dataset_yaml = Path(dataset_yaml)

    log("Dataset preparation completed.")
    log(f"Dataset directory: {dataset_dir}")
    log(f"Dataset YAML: {dataset_yaml}")

    log(
        f"Dataset preparation time: "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    if not dataset_yaml.is_file():

        raise FileNotFoundError(
            f"Dataset YAML not found: {dataset_yaml}"
        )

    # --------------------------------------------------------
    # 2. CHECK DATASET
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log("----------------------------------------")
    log("STEP 2: CHECKING DATASET")
    log("----------------------------------------")

    train_images = count_images(
        dataset_dir / "images" / "train"
    )

    val_images = count_images(
        dataset_dir / "images" / "val"
    )

    test_images = count_images(
        dataset_dir / "images" / "test"
    )

    log(f"Training images: {train_images}")
    log(f"Validation images: {val_images}")
    log(f"Test images: {test_images}")

    if train_images == 0:

        raise RuntimeError(
            "No training images found."
        )

    if has_val and val_images == 0:

        raise RuntimeError(
            "Validation split is marked as available, "
            "but no validation images were found."
        )

    if has_test and test_images == 0:

        raise RuntimeError(
            "Test split is marked as available, "
            "but no test images were found."
        )

    if not has_val:

        raise RuntimeError(
            "No validation split available. "
            "More independent scenes are required."
        )

    log(
        f"Dataset check completed in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # 3. LOAD YOLO MODEL
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log("----------------------------------------")
    log("STEP 3: LOADING YOLO MODEL")
    log("----------------------------------------")

    log(f"Loading model: {MODEL}")

    model = YOLO(MODEL)

    log("YOLO model loaded successfully.")

    log(
        f"Model loading time: "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # 4. PREPARE TRAINING
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    run_name = f"d405_screw_detection_{timestamp}"

    run_directory = OUTPUT_DIR / "runs"

    run_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    log("----------------------------------------")
    log("STEP 4: TRAINING CONFIGURATION")
    log("----------------------------------------")

    log(f"Dataset: {dataset_yaml}")
    log(f"Image size: {IMAGE_SIZE}")
    log(f"Rectangular training: {RECTANGULAR_TRAINING}")
    log(f"Batch size: {BATCH_SIZE}")
    log(f"Epochs: {EPOCHS}")
    log(f"Workers: {WORKERS}")
    log(f"Device: {DEVICE}")
    log(f"Run name: {run_name}")

    # --------------------------------------------------------
    # 5. TRAINING
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log("----------------------------------------")
    log("STEP 5: STARTING MODEL TRAINING")
    log("----------------------------------------")

    results = model.train(

        data=str(dataset_yaml),

        epochs=EPOCHS,

        imgsz=IMAGE_SIZE,

        rect=RECTANGULAR_TRAINING,

        batch=BATCH_SIZE,

        workers=WORKERS,

        lr0=LEARNING_RATE,

        patience=PATIENCE,

        seed=RANDOM_SEED,

        device=DEVICE,

        project=str(run_directory),

        name=run_name,

        exist_ok=True,

        pretrained=True,

        optimizer="auto",

        plots=True,

        save=True,

        save_period=10,

        val=True,

        verbose=True
    )

    training_time = time.perf_counter() - stage_start

    log("----------------------------------------")
    log("MODEL TRAINING COMPLETED")
    log(
        f"Training time: {format_time(training_time)}"
    )
    log("----------------------------------------")

    # --------------------------------------------------------
    # 6. LOCATE BEST WEIGHTS
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log("STEP 6: LOCATING BEST MODEL WEIGHTS")

    best_weights = (
        Path(results.save_dir)
        / "weights"
        / "best.pt"
    )

    if not best_weights.exists():

        raise FileNotFoundError(
            f"Best weights not found: {best_weights}"
        )

    # --------------------------------------------------------
    # 7. COPY WEIGHTS TO FIXED LOCATION
    # --------------------------------------------------------

    fixed_weights_dir = OUTPUT_DIR / "weights"

    fixed_weights_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    fixed_weights = (
        fixed_weights_dir / "best.pt"
    )

    shutil.copy2(
        best_weights,
        fixed_weights
    )

    log(f"Best weights: {best_weights}")
    log(f"Fixed weights: {fixed_weights}")

    log(
        f"Weight handling time: "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # 8. EVALUATE ON TEST SPLIT
    # --------------------------------------------------------

    if has_test and test_images > 0:

        stage_start = time.perf_counter()

        log("----------------------------------------")
        log("STEP 8: EVALUATING ON TEST DATASET")
        log("----------------------------------------")

        best_model = YOLO(
            str(fixed_weights)
        )

        best_model.val(

            data=str(dataset_yaml),

            split="test",

            imgsz=IMAGE_SIZE,

            batch=BATCH_SIZE,

            device=DEVICE,

            project=str(run_directory),

            name=f"{run_name}_test",

            plots=True
        )

        log(
            f"Test evaluation time: "
            f"{format_time(time.perf_counter() - stage_start)}"
        )

    else:

        log(
            "WARNING: No test images available. "
            "Test evaluation skipped."
        )

    # --------------------------------------------------------
    # 9. FINAL REPORT
    # --------------------------------------------------------

    total_time = time.perf_counter() - total_start

    log("========================================")
    log("TRAINING FINISHED")
    log("========================================")

    log(f"Best model: {fixed_weights}")
    log(f"Run directory: {results.save_dir}")
    log(f"Dataset: {dataset_dir}")

    log(
        f"Total training pipeline time: "
        f"{format_time(total_time)}"
    )

    log("========================================")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
