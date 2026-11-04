from __future__ import annotations

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

METADATA_FIELDS = [
    "article_number",
    "filename",
    "relative_path",
    "product_name",
    "din_standard",
    "screw_type",
    "head_type",
    "head_diameter",
    "head_height",
    "tool_type",
    "tool_size",
    "wrench_size",
    "thread_size",
    "thread_pitch",
    "screw_length",
    "shaft_diameter",
    "thread_type",
    "material",
    "strength_class",
    "surface",
    "source_url",
    "source_checked_at",
    "data_quality",
]


def extract_article_number(value: str) -> str | None:
    """
    Extract Würth article number from filename or folder name.

    Example:
        Wuerth_031760_DIN_934.step
    """

    match = re.search(
        r"(?:Wuerth|Würth)[_-](\d{5,10})",
        value,
        re.IGNORECASE,
    )

    return match.group(1) if match else None


def parse_filename(path: Path) -> dict:
    """
    Extract article number and basic DIN information.
    """

    filename = path.stem

    article_number = extract_article_number(filename)

    if article_number is None:
        for parent in path.parents:
            article_number = extract_article_number(parent.name)

            if article_number:
                break

    din_match = re.search(
        r"(DIN|ISO|EN)[_-]?(\d+)",
        filename,
        re.IGNORECASE,
    )

    din_standard = ""

    if din_match:
        din_standard = (
            din_match.group(1).upper()
            + " "
            + din_match.group(2)
        )

    return {
        "article_number": article_number,
        "filename": path.name,
        "din_standard": din_standard,
    }


def load_csv_overrides(
    csv_path: Path,
    input_root: Path,
) -> dict:

    if not csv_path.exists():
        return {}

    overrides = {}

    with csv_path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        reader = csv.DictReader(handle)

        for row in reader:

            article_number = (
                row.get("article_number", "").strip()
            )

            relative_path = (
                row.get("relative_path", "").strip()
            )

            filename = row.get("filename", "").strip()

            if article_number:
                key = article_number

            elif relative_path:
                key = relative_path.replace("\\", "/")

            elif filename:
                key = filename

            else:
                continue

            if key in overrides:
                raise ValueError(
                    f"Doppelter Metadatenschlüssel: {key}"
                )

            overrides[key] = row

    return overrides


def apply_overrides_and_validate(
    path: Path,
    input_root: Path,
    parsed: dict,
    overrides: dict,
) -> dict:

    article_number = parsed.get("article_number")

    relative_path = path.relative_to(
        input_root
    ).as_posix()

    override = overrides.get(article_number)

    if override is None:
        override = overrides.get(relative_path)

    if override is None:
        override = overrides.get(path.name)

    if override is None:
        raise ValueError(
            f"Keine Metadaten für Würth-Artikelnummer "
            f"{article_number} ({path.name}) gefunden."
        )

    labels = {}

    for attribute in ATTRIBUTES:

        value = override.get(attribute, "").strip()

        if not value or value.upper() in {"NA", "N/A", "UNKNOWN"}:
            raise ValueError(
                f"Fehlendes Attribut '{attribute}' "
                f"für Artikelnummer {article_number}"
            )

        labels[attribute] = value

    return labels