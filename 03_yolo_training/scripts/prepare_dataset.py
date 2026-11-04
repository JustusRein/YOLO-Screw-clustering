
import json
import os
import random
import re
import shutil

from datetime import datetime
from pathlib import Path

from PIL import Image


SOURCE_DIR = Path(
    os.environ.get("SOURCE_DIR", "/data/source")
)

OUTPUT_DIR = Path(
    os.environ.get("OUTPUT_DIR", "/workspace/output")
)

RANDOM_SEED = int(
    os.environ.get("RANDOM_SEED", "42")
)

# RGB background used when compositing transparent images.
BACKGROUND_COLOR = (255, 255, 255)


def log(message):
    print(f"[DATASET] {message}", flush=True)


def find_latest_dataset():

    candidates = sorted(
        [
            path
            for path in SOURCE_DIR.glob("screw_dataset_*")
            if path.is_dir()
            and (path / "images").is_dir()
            and (path / "labels").is_dir()
            and (path / "class_mapping.json").is_file()
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if not candidates:
        raise FileNotFoundError(
            f"No valid screw_dataset_* directory found in {SOURCE_DIR}"
        )

    return candidates[0]


def load_classes(source):

    mapping_path = source / "class_mapping.json"

    with mapping_path.open(
        "r",
        encoding="utf-8"
    ) as file:
        mapping = json.load(file)

    if not mapping:
        raise ValueError("class_mapping.json is empty")

    # Sort by numeric class ID.
    classes = sorted(
        mapping.items(),
        key=lambda item: int(item[1])
    )

    ids = [int(class_id) for _, class_id in classes]

    if ids != list(range(len(ids))):
        raise ValueError(
            f"Class IDs must be consecutive starting at zero: {ids}"
        )

    return [name for name, _ in classes]


def model_group_from_filename(image_path):
    """
    Expected image filename:
        00000_STL_FILENAME_00000.png

    The first and last numeric fields are removed so all
    rendered views of the same STL belong to one group.
    """

    stem = image_path.stem

    match = re.match(
        r"^\d+_(.+)_\d+$",
        stem
    )

    if match:
        return match.group(1)

    # Fallback: every image is treated as a separate group.
    return stem


def collect_samples(source, classes):

    samples = []

    for class_id, class_name in enumerate(classes):

        image_dir = source / "images" / class_name
        label_dir = source / "labels" / class_name

        if not image_dir.is_dir():
            log(f"WARNING: Missing image directory: {image_dir}")
            continue

        if not label_dir.is_dir():
            log(f"WARNING: Missing label directory: {label_dir}")
            continue

        for image_path in sorted(image_dir.glob("*.png")):

            label_path = (
                label_dir / f"{image_path.stem}.txt"
            )

            if not label_path.is_file():
                log(f"WARNING: Missing label: {label_path.name}")
                continue

            lines = [
                line.strip()
                for line in label_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]

            if not lines:
                log(f"WARNING: Empty label: {label_path.name}")
                continue

            # Verify YOLO labels.
            for line in lines:
                values = line.split()

                if len(values) != 5:
                    raise ValueError(
                        f"Invalid YOLO label in {label_path}: {line}"
                    )

                label_class = int(values[0])

                if label_class != class_id:
                    raise ValueError(
                        f"Class mismatch in {label_path}: "
                        f"expected {class_id}, got {label_class}"
                    )

                bbox = [float(value) for value in values[1:]]

                if any(value < 0 or value > 1 for value in bbox):
                    raise ValueError(
                        f"Invalid normalized bounding box: {label_path}"
                    )

            samples.append({
                "image": image_path,
                "label": label_path,
                "class_name": class_name,
                "class_id": class_id,
                "model_group": model_group_from_filename(image_path)
            })

    if not samples:
        raise RuntimeError(
            "No valid image/label pairs found."
        )

    return samples


def assign_model_splits(samples):

    """
    Split at source-model level to prevent leakage between
    different rendered views of the same screw.

    Per class:
      1 model  -> train only
      2 models -> train + val
      3-4      -> train + val
      5+       -> train + val + test
    """

    rng = random.Random(RANDOM_SEED)

    groups_by_class = {}

    for sample in samples:

        class_name = sample["class_name"]

        groups_by_class.setdefault(
            class_name,
            {}
        )

        groups_by_class[class_name].setdefault(
            sample["model_group"],
            []
        )

        groups_by_class[class_name][
            sample["model_group"]
        ].append(sample)

    split_by_sample = {}

    for class_name, groups in groups_by_class.items():

        group_names = list(groups.keys())
        rng.shuffle(group_names)

        count = len(group_names)

        val_count = 0
        test_count = 0

        if count >= 2:
            val_count = 1

        if count >= 5:
            test_count = 1

        # Keep at least one source model in train.
        train_count = count - val_count - test_count

        if train_count < 1:
            raise RuntimeError(
                f"Not enough source models for class {class_name}"
            )

        val_groups = set(
            group_names[:val_count]
        )

        test_groups = set(
            group_names[val_count:val_count + test_count]
        )

        log(
            f"{class_name}: {count} source models, "
            f"{train_count} train, "
            f"{val_count} val, "
            f"{test_count} test"
        )

        for group_name, group_samples in groups.items():

            if group_name in val_groups:
                split = "val"

            elif group_name in test_groups:
                split = "test"

            else:
                split = "train"

            for sample in group_samples:
                split_by_sample[
                    sample["image"].as_posix()
                ] = split

    return split_by_sample


def copy_rgb_image(source_path, target_path):

    """
    Preserve transparent source images.
    Composite a separate RGB training image onto white.
    """

    with Image.open(source_path) as image:

        rgba = image.convert("RGBA")

        background = Image.new(
            "RGBA",
            rgba.size,
            BACKGROUND_COLOR + (255,)
        )

        composited = Image.alpha_composite(
            background,
            rgba
        )

        composited.convert("RGB").save(
            target_path,
            format="PNG",
            optimize=True
        )


def write_dataset_yaml(
    dataset_root,
    classes,
    has_val,
    has_test
):

    names = {
        index: name
        for index, name in enumerate(classes)
    }

    yaml_lines = [
        f"path: {dataset_root}",
        "train: images/train",
        "val: images/val" if has_val else "val: images/train",
    ]

    if has_test:
        yaml_lines.append("test: images/test")

    yaml_lines.append("names:")

    for class_id, class_name in names.items():
        yaml_lines.append(
            f"  {class_id}: {json.dumps(class_name)}"
        )

    yaml_path = dataset_root / "dataset.yaml"

    yaml_path.write_text(
        "\n".join(yaml_lines) + "\n",
        encoding="utf-8"
    )

    return yaml_path


def prepare_dataset():

    log("Starting dataset preparation")

    source = find_latest_dataset()

    log(f"Source dataset: {source}")

    classes = load_classes(source)

    log(f"Classes: {classes}")

    samples = collect_samples(
        source,
        classes
    )

    log(f"Valid image/label pairs: {len(samples)}")

    split_by_sample = assign_model_splits(
        samples
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    dataset_root = (
        OUTPUT_DIR
        / "datasets"
        / f"screw_head_dataset_{timestamp}"
    )

    for split in ("train", "val", "test"):

        (dataset_root / "images" / split).mkdir(
            parents=True,
            exist_ok=True
        )

        (dataset_root / "labels" / split).mkdir(
            parents=True,
            exist_ok=True
        )

    counts = {
        "train": 0,
        "val": 0,
        "test": 0
    }

    for sample in samples:

        split = split_by_sample[
            sample["image"].as_posix()
        ]

        target_image = (
            dataset_root
            / "images"
            / split
            / sample["image"].name
        )

        target_label = (
            dataset_root
            / "labels"
            / split
            / sample["label"].name
        )

        copy_rgb_image(
            sample["image"],
            target_image
        )

        shutil.copy2(
            sample["label"],
            target_label
        )

        counts[split] += 1

    has_val = counts["val"] > 0
    has_test = counts["test"] > 0

    if not has_val:
        log(
            "WARNING: No validation images available. "
            "Training will run without validation."
        )

    yaml_path = write_dataset_yaml(
        dataset_root,
        classes,
        has_val,
        has_test
    )

    # Save source information and split statistics.
    report = {
        "source_dataset": str(source),
        "classes": classes,
        "images": counts,
        "total_images": sum(counts.values()),
        "validation_available": has_val,
        "test_available": has_test,
        "split_strategy": "source_model"
    }

    (dataset_root / "dataset_report.json").write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )

    log("Dataset preparation completed")
    log(f"Dataset: {dataset_root}")
    log(f"Images: {counts}")
    log(f"YAML: {yaml_path}")

    return dataset_root, yaml_path, has_val, has_test


if __name__ == "__main__":

    prepare_dataset()
