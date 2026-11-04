from pathlib import Path
from ultralytics import YOLO

DATASET_ROOT = Path("../output/yolo_datasets")
MODEL_ROOT = Path("../output/models")

MODEL_NAME = "yolo26n.pt"
EPOCHS = 100
IMAGE_SIZE = 640
BATCH_SIZE = 16

ATTRIBUTES = [
    "screw_type",
    "tool_size",
    "thread_size",
    "thread_pitch",
    "screw_length"
]


def train_models():

    for attribute in ATTRIBUTES:

        dataset_yaml = (
            DATASET_ROOT /
            attribute /
            "data.yaml"
        )

        if not dataset_yaml.exists():
            print(
                "Dataset missing:",
                attribute
            )
            continue

        print("\nTraining:", attribute)

        model = YOLO(MODEL_NAME)

        model.train(
            data=str(dataset_yaml),
            epochs=EPOCHS,
            imgsz=IMAGE_SIZE,
            batch=BATCH_SIZE,
            project=str(MODEL_ROOT),
            name=attribute,
            exist_ok=True
        )

        print(
            "Finished training:",
            attribute
        )


if __name__ == "__main__":
    train_models()