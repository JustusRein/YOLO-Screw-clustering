"""Filename/CSV metadata parsing for STEP screw dataset generation.

This module intentionally contains no Blender imports so it can be tested with
ordinary Python before starting the rendering pipeline.
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ATTRIBUTES = (
    "screw_type",
    "tool_size",
    "thread_size",
    "thread_pitch",
    "screw_length",
)

# Explicit and editable standard-to-type mapping.
# Add standards only after checking the actual product/standard variant.
DIN_TO_SCREW_TYPE = {
    "DIN_912": "Socket_Head_Cap_Screw",
    "DIN_931": "Hex_Head_Screw",
    "DIN_933": "Hex_Head_Screw",
    "DIN_961": "Hex_Head_Screw",
    "DIN_7984": "Low_Head_Socket_Head_Screw",
    "DIN_7991": "Countersunk_Socket_Head_Screw",
    "DIN_934": "Hex_Nut",
    "ISO_7380": "Button_Head_Screw",
    "ISO_4762": "Socket_Head_Cap_Screw",
}

# Example:
# DIN_912_M5_P0.8_HEX4_L20.step
# DIN_961_M6_P0.75_SW10_L30.step
# DIN_7991_M5_P0.8_HEX3_L16.step
# ISO_7380_M6_P1.0_HEX4_L20.step
# DIN_934_M8_P1.25_SW13_LNA.step
FILENAME_RE = re.compile(
    r"^(?P<standard>(?:DIN|ISO|EN)_\d+[A-Z0-9]*)"
    r"_M(?P<thread>\d+(?:[.,]\d+)?)"
    r"_P(?P<pitch>\d+(?:[.,]\d+)?)"
    r"_(?P<drive>HEX|SW|TX|PH|PZ|SLOT)_?"
    r"(?P<tool>\d+(?:[.,]\d+)?|NA)"
    r"_L(?P<length>\d+(?:[.,]\d+)?|NA)$",
    re.IGNORECASE,
)

def _decimal_text(value: str) -> str:
    try:
        number = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Ungültiger Zahlenwert: {value!r}") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"Zahlenwert muss größer 0 sein: {value!r}")
    text = format(number.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

def normalize_screw_type(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    # Preserve a readable, stable class name.
    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_]+", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value

def normalize_tool_size(value: str) -> str:
    value = str(value).strip().upper().replace(" ", "").replace(",", ".")
    if not value:
        return ""
    match = re.fullmatch(r"(HEX|INBUS|ALLEN|SW|TX|TORX|PH|PZ|SLOT)_?(\d+(?:\.\d+)?|NA)", value)
    if not match:
        raise ValueError(
            f"tool_size muss z. B. HEX4, SW10, TX25, PH2 oder PZ2 sein; erhalten: {value!r}"
        )
    family, number = match.groups()
    family = {"INBUS": "HEX", "ALLEN": "HEX", "TORX": "TX"}.get(family, family)
    return family + (number if number == "NA" else _decimal_text(number))

def normalize_thread_size(value: str) -> str:
    value = str(value).strip().upper().replace(" ", "").replace(",", ".")
    if not value:
        return ""
    match = re.fullmatch(r"M?(\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"thread_size muss z. B. M3, M5 oder M10 sein; erhalten: {value!r}")
    return "M" + _decimal_text(match.group(1))

def normalize_pitch(value: str) -> str:
    value = str(value).strip().upper().replace(" ", "").replace(",", ".")
    if not value:
        return ""
    match = re.fullmatch(r"P?(\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"thread_pitch muss z. B. P0.5, P0.8 oder P1.25 sein; erhalten: {value!r}")
    return "P" + _decimal_text(match.group(1))

def normalize_length(value: str) -> str:
    value = str(value).strip().upper().replace(" ", "").replace(",", ".")
    if not value:
        return ""
    if value in {"NA", "N/A", "NONE"}:
        return "NA"
    match = re.fullmatch(r"L?(\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"screw_length muss z. B. L8, L20 oder NA sein; erhalten: {value!r}")
    return "L" + _decimal_text(match.group(1))

def parse_filename(step_path: Path) -> dict[str, str]:
    stem = step_path.stem
    match = FILENAME_RE.fullmatch(stem)
    if not match:
        raise ValueError(
            "Dateiname entspricht nicht dem erwarteten Schema. "
            "Erwartet: DIN_912_M5_P0.8_HEX4_L20.step"
        )

    standard = match.group("standard").upper()
    drive = match.group("drive").upper()
    tool = match.group("tool").replace(",", ".")
    tool_size = drive + (tool if tool == "NA" else _decimal_text(tool))
    screw_type = DIN_TO_SCREW_TYPE.get(standard, "")

    return {
        "din_standard": standard,
        "screw_type": screw_type,
        "tool_size": normalize_tool_size(tool_size),
        "thread_size": normalize_thread_size(match.group("thread")),
        "thread_pitch": normalize_pitch(match.group("pitch")),
        "screw_length": normalize_length(match.group("length")),
    }

def load_csv_overrides(csv_path: Path, input_root: Path) -> dict[str, dict[str, str]]:
    """Load optional overrides keyed by relative_path or filename.

    Required header:
    filename,screw_type,tool_size,thread_size,thread_pitch,screw_length

    `relative_path` may be used instead of `filename` for duplicate basenames.
    """
    if not csv_path.exists():
        return {}

    overrides: dict[str, dict[str, str]] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV hat keine Kopfzeile: {csv_path}")

        available = {name.strip() for name in reader.fieldnames}
        key_column = "relative_path" if "relative_path" in available else "filename"
        if key_column not in available and "step_file" in available:
            key_column = "step_file"
        if key_column not in available:
            raise ValueError(
                "CSV benötigt eine Spalte 'filename' oder 'relative_path' "
                "(alternativ 'step_file')."
            )

        for line_no, row in enumerate(reader, start=2):
            raw_key = (row.get(key_column) or "").strip()
            if not raw_key:
                continue
            key = raw_key.replace("\\", "/")
            values = {}
            for attr in ATTRIBUTES:
                raw = (row.get(attr) or "").strip()
                if raw:
                    values[attr] = raw
            if key in overrides:
                raise ValueError(f"Doppelter CSV-Schlüssel in Zeile {line_no}: {key}")
            overrides[key] = values
    return overrides

def apply_overrides_and_validate(
    step_path: Path,
    input_root: Path,
    parsed: dict[str, str],
    overrides: dict[str, dict[str, str]],
) -> dict[str, str]:
    relative = step_path.relative_to(input_root).as_posix()
    candidates = (relative, step_path.name, str(step_path))
    row: dict[str, str] = {}
    for key in candidates:
        if key in overrides:
            row = overrides[key]
            break

    result = dict(parsed)
    normalizers = {
        "screw_type": normalize_screw_type,
        "tool_size": normalize_tool_size,
        "thread_size": normalize_thread_size,
        "thread_pitch": normalize_pitch,
        "screw_length": normalize_length,
    }
    for attr, raw in row.items():
        if attr in normalizers:
            result[attr] = normalizers[attr](raw)

    missing = [attr for attr in ATTRIBUTES if not result.get(attr)]
    if missing:
        raise ValueError(
            "Folgende Labels fehlen: " + ", ".join(missing) +
            ". Ergänze den Dateinamen oder die CSV. "
            "Bei Muttern ist screw_length=NA einzutragen."
        )
    return result
