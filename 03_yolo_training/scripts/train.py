
import os
from pathlib import Path

from ultralytics import YOLO

from prepare_dataset import prepare_dataset


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = os.environ.get(
    "MODEL",
    "yolo11n.pt"
)

EPOCHS = int(
    os.environ.get("EPOCHS", "100")
)

IMAGE_SIZE = int(
    os.environ.get("IMAGE_SIZE", "640")
)

BATCH_SIZE = int(
    os.environ.get("BATCH_SIZE", "8")
)

WORKERS = int(
    os.environ.get("WORKERS", "4")
)

LEARNING_RATE = float(
    os.environ.get("LEARNING_RATE", "0.001")
)

PATIENCE = int(
    os.environ.get("PATIENCE", "30")
)

RANDOM_SEED = int(
    os.environ.get("RANDOM_SEED", "42")
)

OUTPUT_DIR = Path(
    os.environ.get("OUTPUT_DIR", "/workspace/output")
)


def log(message):

    print(
        f"[YOLO-TRAINING] {message}",
        flush=True
    )


# ============================================================
# TRAINING
# ============================================================

def main():

    log("Starting YOLO training")

    # --------------------------------------------------------
    # PREPARE DATASET
    # --------------------------------------------------------

    dataset_root, yaml_path, has_val, has_test = (
        prepare_dataset()
    )

    log(f"Dataset: {dataset_root}")
    log(f"Dataset YAML: {yaml_path}")

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    log(f"Loading model: {MODEL_NAME}")

    model = YOLO(MODEL_NAME)

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    run_project = OUTPUT_DIR / "runs"

    log("Starting model training")

    results = model.train(

        data=str(yaml_path),

        epochs=EPOCHS,

        imgsz=IMAGE_SIZE,

        batch=BATCH_SIZE,

        workers=WORKERS,

        lr0=LEARNING_RATE,

        patience=PATIENCE,

        seed=RANDOM_SEED,

        project=str(run_project),

        name="screw_head_type",

        exist_ok=False,

        pretrained=True,

        optimizer="auto",

        save=True,

        save_period=10,

        plots=True,

        verbose=True,

        # Disable validation if no independent validation
        # images exist.
        val=has_val,

        # General augmentation
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.3,

        degrees=25.0,
        translate=0.1,
        scale=0.3,

        shear=3.0,
        perspective=0.0,

        flipud=0.0,
        fliplr=0.5,

        mosaic=0.5,
        mixup=0.0,

        close_mosaic=10
    )

    # --------------------------------------------------------
    # BEST WEIGHTS
    # --------------------------------------------------------

    save_dir = Path(
        model.trainer.save_dir
    )

    best_weights = (
        save_dir
        / "weights"
        / "best.pt"
    )

    last_weights = (
        save_dir
        / "weights"
        / "last.pt"
    )

    log("Training completed")

    log(f"Results directory: {save_dir}")
    log(f"Best weights: {best_weights}")
    log(f"Last weights: {last_weights}")

    # --------------------------------------------------------
    # TEST EVALUATION
    # --------------------------------------------------------

    if has_test and best_weights.exists():

        log("Starting independent test evaluation")

        best_model = YOLO(
            str(best_weights)
        )

        test_results = best_model.val(
            data=str(yaml_path),
            split="test",
            imgsz=IMAGE_SIZE,
            batch=BATCH_SIZE,
            workers=WORKERS,
            project=str(run_project),
            name="screw_head_type_test",
            exist_ok=True
        )

        log("Test evaluation completed")

    else:

        log(
            "No independent test set available. "
            "No test evaluation was performed."
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    log("====================================")
    log("YOLO TRAINING FINISHED")
    log("====================================")

    log(f"Model: {MODEL_NAME}")
    log(f"Epochs: {EPOCHS}")
    log(f"Image size: {IMAGE_SIZE}")
    log(f"Batch size: {BATCH_SIZE}")
    log(f"Best weights: {best_weights}")
    log(f"Training output: {save_dir}")


if __name__ == "__main__":

    main()
