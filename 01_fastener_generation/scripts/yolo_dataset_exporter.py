from pathlib import Path
import csv
import shutil
import random

ATTRIBUTES = {
    "screw_type": "screw_type",
    "tool_size": "tool_size",
    "thread_size": "thread_size",
    "thread_pitch": "thread_pitch",
    "screw_length": "screw_length"
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def load_metadata(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return {
            row["filename"]: row
            for row in csv.DictReader(f)
        }


def get_class_mapping(metadata, attribute):
    values = sorted({
        row[attribute]
        for row in metadata.values()
        if row.get(attribute, "").strip()
        and row[attribute].strip().upper() != "NA"
    })

    return {
        value: index
        for index, value in enumerate(values)
    }


def export_dataset(
    image_folder,
    label_folder,
    metadata_csv,
    output_folder,
    train_ratio=0.8,
    seed=42
):
    image_folder = Path(image_folder)
    label_folder = Path(label_folder)
    output_folder = Path(output_folder)

    metadata = load_metadata(metadata_csv)

    images = [
        path for path in image_folder.rglob("*")
        if path.suffix.lower() in IMAGE_EXTENSIONS
    ]

    random.seed(seed)
    random.shuffle(images)

    split_index = int(len(images) * train_ratio)

    splits = {
        "train": images[:split_index],
        "val": images[split_index:]
    }

    for dataset_name, attribute in ATTRIBUTES.items():

        class_mapping = get_class_mapping(
            metadata,
            attribute
        )

        dataset_root = output_folder / dataset_name

        for split in splits:
            (dataset_root / "images" / split).mkdir(
                parents=True,
                exist_ok=True
            )

            (dataset_root / "labels" / split).mkdir(
                parents=True,
                exist_ok=True
            )

        for split, split_images in splits.items():

            for image_path in split_images:

                label_path = (
                    label_folder /
                    image_path.relative_to(image_folder)
                ).with_suffix(".txt")

                if not label_path.exists():
                    continue

                # Metadata lookup based on the image filename stem.
                # Adapt this mapping if your renderer uses another naming scheme.
                metadata_entry = metadata.get(image_path.stem)

                if metadata_entry is None:
                    continue

                value = metadata_entry.get(attribute, "").strip()

                if value not in class_mapping:
                    continue

                class_id = class_mapping[value]

                with label_path.open("r") as f:
                    original_labels = f.readlines()

                new_labels = []

                for line in original_labels:
                    parts = line.strip().split()

                    if len(parts) != 5:
                        continue

                    # Reuse the original bounding box.
                    new_labels.append(
                        f"{class_id} " + " ".join(parts[1:])
                    )

                if not new_labels:
                    continue

                destination_image = (
                    dataset_root / "images" / split /
                    image_path.name
                )

                destination_label = (
                    dataset_root / "labels" / split /
                    image_path.with_suffix(".txt").name
                )

                shutil.copy2(
                    image_path,
                    destination_image
                )

                destination_label.write_text(
                    "\n".join(new_labels) + "\n"
                )

        # Generate YOLO configuration.
        yaml_path = dataset_root / "data.yaml"

        yaml_content = [
            f"path: {dataset_root.resolve()}",
            "train: images/train",
            "val: images/val",
            f"nc: {len(class_mapping)}",
            "names:"
        ]

        for value, class_id in class_mapping.items():
            yaml_content.append(
                f"  {class_id}: '{value}'"
            )

        yaml_path.write_text(
            "\n".join(yaml_content),
            encoding="utf-8"
        )

        print("Created dataset:", dataset_name)


if __name__ == "__main__":

    export_dataset(
        image_folder="../output/images",
        label_folder="../output/labels",
        metadata_csv="../input/screw_metadata.csv",
        output_folder="../output/yolo_datasets"
    )