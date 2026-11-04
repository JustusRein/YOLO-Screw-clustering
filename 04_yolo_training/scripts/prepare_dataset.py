
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import time

from datetime import datetime
from pathlib import Path

from PIL import Image


# ============================================================
# CONFIGURATION
# ============================================================

SOURCE_DIR = Path(os.environ.get(
    "SOURCE_DIR", "/data/source"
))

OUTPUT_DIR = Path(os.environ.get(
    "OUTPUT_DIR", "/workspace/output"
))

RANDOM_SEED = int(os.environ.get(
    "RANDOM_SEED", "42"
))

# Expected Intel RealSense D405 image resolution
EXPECTED_WIDTH = int(os.environ.get(
    "EXPECTED_WIDTH", "1280"
))

EXPECTED_HEIGHT = int(os.environ.get(
    "EXPECTED_HEIGHT", "720"
))

# Split happens here, not during Blender generation.
TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

# Progress logging interval
LOG_INTERVAL = 25

random.seed(RANDOM_SEED)


# ============================================================
# LOGGING
# ============================================================

def log(message):

    print(
        f"[DATASET] {message}",
        flush=True
    )


def format_time(seconds):

    if seconds < 60:
        return f"{seconds:.2f} seconds"

    minutes = int(seconds // 60)
    remaining = seconds % 60

    return f"{minutes} min {remaining:.1f} sec"


# ============================================================
# FIND SOURCE DATASET
# ============================================================

def find_latest_dataset():

    candidates = sorted(
        [
            path
            for path in SOURCE_DIR.glob("multi_object_dataset_*")
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
            f"No valid multi_object_dataset_* directory found "
            f"in {SOURCE_DIR}"
        )

    return candidates[0]


# ============================================================
# LOAD CLASSES
# ============================================================

def load_classes(source):

    mapping_path = source / "class_mapping.json"

    with mapping_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        mapping = json.load(file)

    if not mapping:
        raise ValueError("class_mapping.json is empty")

    classes = sorted(
        mapping.items(),
        key=lambda item: int(item[1])
    )

    ids = [
        int(class_id)
        for _, class_id in classes
    ]

    if ids != list(range(len(ids))):

        raise ValueError(
            f"Class IDs must be consecutive starting at zero: {ids}"
        )

    return [
        name
        for name, _ in classes
    ]


# ============================================================
# VALIDATE YOLO LABELS
# ============================================================

def validate_label_file(label_path, number_of_classes):

    if not label_path.exists():

        raise FileNotFoundError(
            f"Missing label file: {label_path}"
        )

    lines = [
        line.strip()
        for line in label_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    # Empty labels are valid.
    # They represent images without labelled fasteners.
    if not lines:
        return 0

    for line_number, line in enumerate(lines, start=1):

        values = line.split()

        if len(values) != 5:

            raise ValueError(
                f"Invalid YOLO label in {label_path}, "
                f"line {line_number}: {line}"
            )

        try:

            class_id = int(values[0])

            bbox = [
                float(value)
                for value in values[1:]
            ]

        except ValueError as error:

            raise ValueError(
                f"Non-numeric label value in {label_path}: {line}"
            ) from error

        if class_id < 0 or class_id >= number_of_classes:

            raise ValueError(
                f"Invalid class ID {class_id} in {label_path}"
            )

        if any(
            value < 0 or value > 1
            for value in bbox
        ):

            raise ValueError(
                f"Bounding box outside normalized range "
                f"in {label_path}: {line}"
            )

        x_center, y_center, width, height = bbox

        if width <= 0 or height <= 0:

            raise ValueError(
                f"Bounding box has zero or negative size: {label_path}"
            )

        if (
            x_center - width / 2 < -0.001
            or x_center + width / 2 > 1.001
            or y_center - height / 2 < -0.001
            or y_center + height / 2 > 1.001
        ):

            raise ValueError(
                f"Bounding box exceeds image boundaries: {label_path}"
            )

    return len(lines)


# ============================================================
# COLLECT SCENES
# ============================================================

def collect_samples(source, classes):

    image_dir = source / "images"
    label_dir = source / "labels"

    image_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp"
    }

    image_paths = sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in image_extensions
    )

    if not image_paths:

        raise RuntimeError(
            f"No images found in {image_dir}"
        )

    samples = []

    dimension_warnings = 0

    log(f"Found {len(image_paths)} source images.")
    log("Validating images and YOLO labels...")

    for index, image_path in enumerate(image_paths, start=1):

        label_path = (
            label_dir
            / f"{image_path.stem}.txt"
        )

        try:

            number_of_boxes = validate_label_file(
                label_path,
                len(classes)
            )

            # Read image dimensions without converting or resizing.
            with Image.open(image_path) as image:

                width, height = image.size

                image_mode = image.mode

            if (
                width != EXPECTED_WIDTH
                or height != EXPECTED_HEIGHT
            ):

                dimension_warnings += 1

                log(
                    f"WARNING: {image_path.name} has "
                    f"{width}x{height}, expected "
                    f"{EXPECTED_WIDTH}x{EXPECTED_HEIGHT}"
                )

            samples.append({
                "image": image_path,
                "label": label_path,
                "boxes": number_of_boxes,
                "width": width,
                "height": height,
                "mode": image_mode
            })

        except Exception as error:

            log(
                f"WARNING: Skipping {image_path.name}: {error}"
            )

        if (
            index % LOG_INTERVAL == 0
            or index == len(image_paths)
        ):

            log(
                f"Validated {index}/{len(image_paths)} images "
                f"({len(samples)} valid)"
            )

    if not samples:

        raise RuntimeError(
            "No valid image/label pairs found."
        )

    log(
        f"Resolution check finished. "
        f"Images with unexpected resolution: {dimension_warnings}"
    )

    return samples


# ============================================================
# CREATE SOURCE FINGERPRINT
# ============================================================

def create_source_fingerprint(source, samples, classes):

    """
    Creates a fingerprint from the source dataset.

    If an image or label changes, its file size or modification
    timestamp changes and the cached dataset is regenerated.
    """

    fingerprint_data = {
        "source": str(source.resolve()),
        "classes": classes,
        "random_seed": RANDOM_SEED,
        "train_ratio": TRAIN_RATIO,
        "val_ratio": VAL_RATIO,
        "test_ratio": TEST_RATIO,
        "expected_width": EXPECTED_WIDTH,
        "expected_height": EXPECTED_HEIGHT,
        "files": []
    }

    for sample in samples:

        for path in (
            sample["image"],
            sample["label"]
        ):

            stat = path.stat()

            fingerprint_data["files"].append({
                "name": path.name,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns
            })

    serialized = json.dumps(
        fingerprint_data,
        sort_keys=True
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


# ============================================================
# SPLIT SCENES
# ============================================================

def assign_scene_splits(samples):

    """
    Split complete scenes, not individual bounding boxes.

    All objects and labels belonging to one rendered scene
    remain together in the same split.
    """

    rng = random.Random(RANDOM_SEED)

    shuffled = list(samples)
    rng.shuffle(shuffled)

    count = len(shuffled)

    if count == 1:

        return {
            shuffled[0]["image"].name: "train"
        }

    if count == 2:

        return {
            shuffled[0]["image"].name: "train",
            shuffled[1]["image"].name: "val"
        }

    train_count = max(
        1,
        int(count * TRAIN_RATIO)
    )

    val_count = max(
        1,
        int(count * VAL_RATIO)
    )

    test_count = count - train_count - val_count

    if test_count < 1:

        test_count = 1
        train_count = count - val_count - test_count

    if train_count < 1:

        raise RuntimeError(
            "Not enough scenes for train/val/test splitting."
        )

    split_by_image = {}

    for index, sample in enumerate(shuffled):

        if index < train_count:
            split = "train"

        elif index < train_count + val_count:
            split = "val"

        else:
            split = "test"

        split_by_image[
            sample["image"].name
        ] = split

    return split_by_image


# ============================================================
# COPY IMAGES
# ============================================================

def copy_image(source_path, target_path):

    """
    Fast copy for images already in RGB mode.

    No unnecessary PNG recompression is performed.
    Images requiring conversion are converted to RGB.
    """

    with Image.open(source_path) as image:

        if image.mode == "RGB":

            # Direct copy without recompression.
            shutil.copy2(
                source_path,
                target_path
            )

            return

        # Convert only when required.
        image.convert("RGB").save(
            target_path,
            format=image.format
        )

    # Preserve source modification time.
    shutil.copystat(
        source_path,
        target_path
    )


# ============================================================
# WRITE DATASET YAML
# ============================================================

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
        "val: images/val" if has_val else "val: images/train"
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


# ============================================================
# CHECK EXISTING DATASET CACHE
# ============================================================

def check_cached_dataset(
    dataset_root,
    fingerprint,
    samples
):

    """
    Reuse an existing prepared dataset if:

    - Its source fingerprint matches.
    - Its YAML file exists.
    - All expected images and labels exist.
    """

    report_path = dataset_root / "dataset_report.json"
    yaml_path = dataset_root / "dataset.yaml"

    if not report_path.is_file() or not yaml_path.is_file():
        return False

    try:

        with report_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            report = json.load(file)

        if report.get("source_fingerprint") != fingerprint:
            return False

        for sample in samples:

            image_name = sample["image"].name
            label_name = sample["label"].name

            split = report["split_by_image"][image_name]

            image_target = (
                dataset_root
                / "images"
                / split
                / image_name
            )

            label_target = (
                dataset_root
                / "labels"
                / split
                / label_name
            )

            if not image_target.is_file():
                return False

            if not label_target.is_file():
                return False

        return True

    except Exception:

        return False


# ============================================================
# LOAD CACHED DATASET
# ============================================================

def load_cached_dataset(dataset_root):

    report_path = dataset_root / "dataset_report.json"
    yaml_path = dataset_root / "dataset.yaml"

    with report_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        report = json.load(file)

    counts = report["images"]

    has_val = counts["val"] > 0
    has_test = counts["test"] > 0

    log("========================================")
    log("EXISTING DATASET CACHE FOUND")
    log("========================================")

    log(f"Reusing dataset: {dataset_root}")
    log(f"Images: {counts}")
    log(f"Labelled objects: {report['labelled_objects']}")
    log(f"YAML: {yaml_path}")

    return dataset_root, yaml_path, has_val, has_test


# ============================================================
# MAIN DATASET PREPARATION
# ============================================================

def prepare_dataset():

    total_start = time.perf_counter()

    log("========================================")
    log("STARTING DATASET PREPARATION")
    log("========================================")

    log(
        f"Expected image resolution: "
        f"{EXPECTED_WIDTH}x{EXPECTED_HEIGHT}"
    )

    # --------------------------------------------------------
    # FIND SOURCE DATASET
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    source = find_latest_dataset()

    log(f"Source dataset: {source}")

    classes = load_classes(source)

    log(f"Classes: {classes}")

    log(
        f"Source lookup completed in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # COLLECT AND VALIDATE SAMPLES
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    samples = collect_samples(
        source,
        classes
    )

    log(f"Valid scenes: {len(samples)}")

    log(
        f"Labelled fasteners: "
        f"{sum(sample['boxes'] for sample in samples)}"
    )

    log(
        f"Scenes without labelled fasteners: "
        f"{sum(1 for sample in samples if sample['boxes'] == 0)}"
    )

    log(
        f"Validation completed in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # CREATE FINGERPRINT
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    fingerprint = create_source_fingerprint(
        source,
        samples,
        classes
    )

    log(f"Source fingerprint: {fingerprint[:16]}...")

    # --------------------------------------------------------
    # CACHE DIRECTORY
    # --------------------------------------------------------

    dataset_root = (
        OUTPUT_DIR
        / "datasets"
        / f"screw_scene_dataset_{source.name}_seed{RANDOM_SEED}"
    )

    # --------------------------------------------------------
    # CHECK CACHE
    # --------------------------------------------------------

    if check_cached_dataset(
        dataset_root,
        fingerprint,
        samples
    ):

        result = load_cached_dataset(
            dataset_root
        )

        log(
            f"Total preparation time: "
            f"{format_time(time.perf_counter() - total_start)}"
        )

        return result

    log("No valid dataset cache found.")
    log("Creating a new prepared dataset...")

    # Remove incomplete or outdated cached dataset.
    if dataset_root.exists():

        log("Removing outdated dataset cache...")

        shutil.rmtree(dataset_root)

    # --------------------------------------------------------
    # SPLIT SCENES
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    split_by_image = assign_scene_splits(
        samples
    )

    log(
        f"Scene splitting completed in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # CREATE DIRECTORIES
    # --------------------------------------------------------

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

    box_counts = {
        "train": 0,
        "val": 0,
        "test": 0
    }

    negative_counts = {
        "train": 0,
        "val": 0,
        "test": 0
    }

    # --------------------------------------------------------
    # COPY SCENES
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    log(f"Copying {len(samples)} images and labels...")

    for index, sample in enumerate(samples, start=1):

        image_name = sample["image"].name

        split = split_by_image[image_name]

        target_image = (
            dataset_root
            / "images"
            / split
            / image_name
        )

        target_label = (
            dataset_root
            / "labels"
            / split
            / sample["label"].name
        )

        copy_image(
            sample["image"],
            target_image
        )

        shutil.copy2(
            sample["label"],
            target_label
        )

        counts[split] += 1
        box_counts[split] += sample["boxes"]

        if sample["boxes"] == 0:
            negative_counts[split] += 1

        if (
            index % LOG_INTERVAL == 0
            or index == len(samples)
        ):

            elapsed = time.perf_counter() - stage_start

            log(
                f"Copied {index}/{len(samples)} images "
                f"({format_time(elapsed)})"
            )

    log(
        f"Image copying completed in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # DATASET YAML
    # --------------------------------------------------------

    stage_start = time.perf_counter()

    has_val = counts["val"] > 0
    has_test = counts["test"] > 0

    yaml_path = write_dataset_yaml(
        dataset_root,
        classes,
        has_val,
        has_test
    )

    log(
        f"Dataset YAML created in "
        f"{format_time(time.perf_counter() - stage_start)}"
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = {
        "source_dataset": str(source),
        "source_fingerprint": fingerprint,
        "classes": classes,
        "images": counts,
        "labelled_objects": box_counts,
        "negative_scenes": negative_counts,
        "total_images": sum(counts.values()),
        "total_labelled_objects": sum(box_counts.values()),
        "split_strategy": "scene_level_random",
        "train_ratio": TRAIN_RATIO,
        "val_ratio": VAL_RATIO,
        "test_ratio": TEST_RATIO,
        "random_seed": RANDOM_SEED,
        "expected_resolution": {
            "width": EXPECTED_WIDTH,
            "height": EXPECTED_HEIGHT
        },
        "split_by_image": split_by_image,
        "created_at": datetime.now().isoformat()
    }

    (dataset_root / "dataset_report.json").write_text(
        json.dumps(
            report,
            indent=4
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------

    log("========================================")
    log("DATASET PREPARATION FINISHED")
    log("========================================")

    log(f"Dataset: {dataset_root}")
    log(f"Images: {counts}")
    log(f"Labelled objects: {box_counts}")
    log(f"Negative scenes: {negative_counts}")
    log(f"YAML: {yaml_path}")

    log(
        f"Total preparation time: "
        f"{format_time(time.perf_counter() - total_start)}"
    )

    return dataset_root, yaml_path, has_val, has_test


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    prepare_dataset()
