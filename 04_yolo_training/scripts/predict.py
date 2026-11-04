import os
from pathlib import Path
from datetime import datetime

from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

WEIGHTS = Path(os.environ.get(
    "WEIGHTS",
    "/workspace/output/weights/best.pt"
))

INPUT_DIR = Path(os.environ.get(
    "PREDICT_DIR",
    "/data/predict"
))

OUTPUT_DIR = Path(os.environ.get(
    "OUTPUT_DIR",
    "/workspace/output"
))

IMAGE_SIZE = int(os.environ.get(
    "IMAGE_SIZE",
    "1280"
))

CONFIDENCE = float(os.environ.get(
    "CONFIDENCE",
    "0.25"
))

IOU_THRESHOLD = float(os.environ.get(
    "IOU_THRESHOLD",
    "0.45"
))

DEVICE = os.environ.get(
    "DEVICE",
    "cpu"
)


# ============================================================
# HELPERS
# ============================================================

def log(message):
    print(f"[YOLO PREDICTION] {message}", flush=True)


def find_images(directory):

    extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp"
    }

    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
    )


# ============================================================
# MAIN
# ============================================================

def main():

    log("Starting YOLO prediction")

    if not WEIGHTS.exists():

        raise FileNotFoundError(
            f"Model weights not found: {WEIGHTS}\n"
            "Train the model first."
        )

    if not INPUT_DIR.exists():

        raise FileNotFoundError(
            f"Prediction input directory not found: {INPUT_DIR}"
        )

    images = find_images(INPUT_DIR)

    if not images:

        raise RuntimeError(
            f"No images found in {INPUT_DIR}"
        )

    log(f"Model: {WEIGHTS}")
    log(f"Input images: {len(images)}")
    log(f"Image size: {IMAGE_SIZE}")

    model = YOLO(
        str(WEIGHTS)
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    prediction_directory = (
        OUTPUT_DIR
        / "predictions"
        / f"d405_prediction_{timestamp}"
    )

    prediction_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    for image_path in images:

        log(f"Processing: {image_path.name}")

        results = model.predict(

            source=str(image_path),

            imgsz=IMAGE_SIZE,

            conf=CONFIDENCE,

            iou=IOU_THRESHOLD,

            device=DEVICE,

            save=True,

            save_txt=True,

            save_conf=True,

            project=str(prediction_directory),

            name="results",

            exist_ok=True,

            verbose=False
        )

        for result in results:

            if result.boxes is None:
                continue

            for box in result.boxes:

                class_id = int(
                    box.cls.item()
                )

                confidence = float(
                    box.conf.item()
                )

                class_name = model.names[class_id]

                log(
                    f"  {class_name}: "
                    f"{confidence:.3f}"
                )

    log("-----------------------------------")
    log("PREDICTION FINISHED")
    log(f"Results: {prediction_directory}")
    log("-----------------------------------")


if __name__ == "__main__":
    main()