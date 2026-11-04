
import csv
import re
from pathlib import Path


ATTRIBUTES = [
    "screw_type",
    "tool_size",
    "thread_size",
    "thread_pitch",
    "screw_length",
]


def clean_class(value):
    """Convert a metadata value into a valid YOLO class name."""
    value = str(value).strip()
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_")


def load_metadata(csv_path):
    """
    Read generated_metadata.csv from the FreeCAD project.

    Returns:
        Dictionary keyed by STL filename.
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Metadata CSV not found: {csv_path}"
        )

    metadata = {}

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        required = {"stl_file", *ATTRIBUTES}
        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing CSV columns: {sorted(missing)}"
            )

        for row in reader:
            filename = Path(
                row["stl_file"].strip()
            ).name

            if not filename:
                continue

            if filename in metadata:
                raise ValueError(
                    f"Duplicate STL entry in metadata: {filename}"
                )

            labels = {}

            for attribute in ATTRIBUTES:
                value = row.get(attribute, "").strip()

                if not value or value.upper() in {
                    "NA", "N/A", "UNKNOWN", "NONE"
                }:
                    raise ValueError(
                        f"Missing label '{attribute}' "
                        f"for {filename}"
                    )

                labels[attribute] = clean_class(value)

            metadata[filename] = labels

    return metadata
