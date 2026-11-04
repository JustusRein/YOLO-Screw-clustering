
import os
from pathlib import Path

from ultralytics import YOLO


WEIGHTS = Path(
    os.environ.get(
        "WEIGHTS",
        "/workspace/output/runs/screw_head_type/weights/best.pt"
    )
)

INPUT_DIR = Path(
    os.environ.get(
        "PREDICT_INPUT",
        "/data/predict"
    )
)

OUTPUT_DIR = Path(
    os.environ.get(
        "PREDICT_OUTPUT",
        "/workspace/output/predictions"
    )
)

IMAGE_SIZE = int(
    os.environ.get("IMAGE_SIZE", "640")
)

CONFIDENCE = float(
    os.environ.get("CONFIDENCE", "0.25")
)


def main():

    print("[PREDICT] Loading model")

    if not WEIGHTS.exists():
        raise FileNotFoundError(
            f"Model weights not found: {WEIGHTS}"
        )

    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Prediction input directory not found: {INPUT_DIR}"
        )

    images = [
        path
        for path in INPUT_DIR.iterdir()
        if path.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".bmp"
        }
    ]

    if not images:
        raise RuntimeError(
            f"No images found in {INPUT_DIR}"
        )

    model = YOLO(str(WEIGHTS))

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        f"[PREDICT] Processing {len(images)} images"
    )

    results = model.predict(
        source=[str(path) for path in images],
        imgsz=IMAGE_SIZE,
        conf=CONFIDENCE,
        save=True,
        save_txt=True,
        save_conf=True,
        project=str(OUTPUT_DIR),
        name="screw_predictions",
        exist_ok=True
    )

    print("[PREDICT] Finished")

    print(
        f"[PREDICT] Results: {OUTPUT_DIR / 'screw_predictions'}"
    )


if __name__ == "__main__":

    main()
