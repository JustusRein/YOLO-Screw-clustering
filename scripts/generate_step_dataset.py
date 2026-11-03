"""Generate five independent YOLO detection datasets from STEP screw files.

Runs inside Blender. STEP conversion is provided by the StepForge package.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, "/opt")
from stepforge.core import convert_step  # noqa: E402

from metadata import ATTRIBUTES, parse_filename, load_csv_overrides, apply_overrides_and_validate

INPUT_ROOT = Path(os.environ.get("INPUT_DIR", "/data/input"))
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_DIR", "/data/output"))
CSV_PATH = Path(os.environ.get("METADATA_CSV", str(INPUT_ROOT / "screw_metadata.csv")))
IMAGES_PER_STEP = int(os.environ.get("IMAGES_PER_STEP", "30"))
RES_X = int(os.environ.get("RES_X", "640"))
RES_Y = int(os.environ.get("RES_Y", "640"))
STEP_DEFLECTION = float(os.environ.get("STEP_DEFLECTION", "0.025"))
RANDOM_SEED = int(os.environ.get("RANDOM_SEED", "42"))
TRAIN_RATIO = float(os.environ.get("TRAIN_RATIO", "0.70"))
VAL_RATIO = float(os.environ.get("VAL_RATIO", "0.20"))
MAX_RENDER_ATTEMPTS = int(os.environ.get("MAX_RENDER_ATTEMPTS", "20"))

random.seed(RANDOM_SEED)

def log(message: str) -> None:
    print(f"[STEP-YOLO] {message}", flush=True)

def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("._") or "unnamed"

def setup_scene():
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False

    world = scene.world or bpy.data.worlds.new("ScrewDatasetWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.22, 0.22, 0.22, 1)
    bg.inputs["Strength"].default_value = 0.8

    camera_data = bpy.data.cameras.new("DatasetCamera")
    camera = bpy.data.objects.new("DatasetCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.data.lens = 50
    camera.data.sensor_width = 36
    camera.data.clip_start = 0.00001
    camera.data.clip_end = 1000
    scene.camera = camera

    light_data = bpy.data.lights.new("DatasetAreaLight", "AREA")
    light = bpy.data.objects.new("DatasetAreaLight", light_data)
    scene.collection.objects.link(light)
    light.data.shape = "DISK"
    light.data.size = 0.025
    light.data.energy = 1200
    return camera, light

def aim_at(obj, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()

def import_step_as_mesh_objects(step_path: Path):
    """Tessellate STEP solids and create one Blender mesh object per solid.

    StepForge applies STEP assembly instance matrices to each returned solid.
    All solids from one STEP file are kept together as one labelled screw.
    """
    solids = convert_step(
        str(step_path),
        deflection=STEP_DEFLECTION,
        keep_surfaces=False,
        parallel=False,
    )
    valid = [s for s in solids if s.mesh.verts and s.mesh.faces]
    if not valid:
        raise RuntimeError("StepForge hat keine renderbaren Solids erzeugt.")

    all_vertices = [v for solid in valid for v in solid.mesh.verts]
    lo = Vector((
        min(v[0] for v in all_vertices),
        min(v[1] for v in all_vertices),
        min(v[2] for v in all_vertices),
    ))
    hi = Vector((
        max(v[0] for v in all_vertices),
        max(v[1] for v in all_vertices),
        max(v[2] for v in all_vertices),
    ))
    center = (lo + hi) * 0.5
    size = hi - lo

    objects = []
    material = bpy.data.materials.get("ScrewSteel")
    if material is None:
        material = bpy.data.materials.new("ScrewSteel")
        material.diffuse_color = (0.48, 0.52, 0.58, 1)
        material.metallic = 0.25
        material.roughness = 0.38

    for index, solid in enumerate(valid):
        vertices = [
            (float(v[0] - center.x), float(v[1] - center.y), float(v[2] - center.z))
            for v in solid.mesh.verts
        ]
        mesh = bpy.data.meshes.new(f"{safe_name(solid.name)}_{index:03d}_Mesh")
        mesh.from_pydata(vertices, [], solid.mesh.faces)
        mesh.update()
        mesh.materials.append(material)

        obj = bpy.data.objects.new(f"{safe_name(solid.name)}_{index:03d}", mesh)
        bpy.context.scene.collection.objects.link(obj)
        objects.append(obj)

    return objects, size, solids

def object_world_corners(obj):
    bpy.context.view_layer.update()
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

def all_world_corners(objects):
    return [point for obj in objects for point in object_world_corners(obj)]

def compute_yolo_bbox(objects, camera):
    scene = bpy.context.scene
    projected = [
        world_to_camera_view(scene, camera, point)
        for point in all_world_corners(objects)
    ]
    if not projected or any(p.z <= 0 for p in projected):
        return None

    x_min = min(p.x for p in projected)
    x_max = max(p.x for p in projected)
    y_min = min(p.y for p in projected)
    y_max = max(p.y for p in projected)

    # Do not clip boxes: a clipped box would no longer be the true projected
    # extent. The caller retries with another view.
    if x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1:
        return None
    if x_max <= x_min or y_max <= y_min:
        return None

    return (
        (x_min + x_max) / 2,
        1 - (y_min + y_max) / 2,
        x_max - x_min,
        y_max - y_min,
    )

def position_camera_and_light(camera, light, max_dimension: float):
    azimuth = random.uniform(0, 2 * math.pi)
    elevation = math.radians(random.uniform(18, 78))
    distance = max(max_dimension, 0.001) * random.uniform(2.8, 3.8)
    target = Vector((0, 0, 0))

    camera.location = (
        distance * math.cos(elevation) * math.cos(azimuth),
        distance * math.cos(elevation) * math.sin(azimuth),
        distance * math.sin(elevation),
    )
    aim_at(camera, target)

    light.location = (
        camera.location.x * random.uniform(0.65, 1.0),
        camera.location.y * random.uniform(0.65, 1.0),
        abs(camera.location.z) * random.uniform(0.8, 1.4) + max_dimension,
    )
    light.data.energy = random.uniform(700, 1700)
    light.data.size = max(max_dimension * random.uniform(0.6, 1.2), 0.005)
    aim_at(light, target)

    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    shade = random.uniform(0.12, 0.48)
    bg.inputs["Color"].default_value = (shade, shade, shade, 1)

def prepare_random_orientation(objects):
    rotation = (
        math.radians(random.uniform(-25, 25)),
        math.radians(random.uniform(-25, 25)),
        math.radians(random.uniform(0, 360)),
    )
    for obj in objects:
        obj.location = (0, 0, 0)
        obj.rotation_euler = rotation
    bpy.context.view_layer.update()

def create_output_structure(output_root: Path):
    for attribute in ATTRIBUTES:
        for split in ("train", "val", "test"):
            (output_root / attribute / "images" / split).mkdir(parents=True, exist_ok=True)
            (output_root / attribute / "labels" / split).mkdir(parents=True, exist_ok=True)

def make_split_map(records):
    """Split by STEP file, not by rendered image, to avoid data leakage."""
    shuffled = list(records)
    random.Random(RANDOM_SEED).shuffle(shuffled)
    n = len(shuffled)
    if n == 1:
        counts = (1, 0, 0)
    elif n == 2:
        counts = (1, 1, 0)
    else:
        n_train = max(1, int(n * TRAIN_RATIO))
        n_val = max(1, int(n * VAL_RATIO))
        if n_train + n_val >= n:
            n_train = max(1, n - 2)
            n_val = 1
        counts = (n_train, n_val, n - n_train - n_val)

    split_map = {}
    cursor = 0
    for split, count in zip(("train", "val", "test"), counts):
        for record in shuffled[cursor:cursor + count]:
            split_map[str(record["path"])] = split
        cursor += count
    return split_map

def write_yaml(path: Path, dataset_root: Path, class_names: list[str]):
    # JSON arrays and quoted strings are valid YAML and avoid escaping issues.
    content = (
        f"path: {json.dumps(dataset_root.as_posix())}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"nc: {len(class_names)}\n"
        f"names: {json.dumps(class_names, ensure_ascii=False)}\n"
    )
    path.write_text(content, encoding="utf-8")

def write_class_files(output_root: Path, class_maps: dict[str, dict[str, int]]):
    for attribute, mapping in class_maps.items():
        names = [name for name, _ in sorted(mapping.items(), key=lambda item: item[1])]
        dataset_dir = output_root / attribute
        (dataset_dir / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
        write_yaml(output_root / f"data_{attribute}.yaml", dataset_dir, names)

def render_record(record, file_index, split, class_maps, output_root, camera, light):
    step_path = record["path"]
    labels = record["labels"]
    objects = []
    successful = 0
    try:
        objects, dimensions, _solids = import_step_as_mesh_objects(step_path)
        max_dimension = max(float(dimensions.x), float(dimensions.y), float(dimensions.z), 0.001)

        for image_index in range(IMAGES_PER_STEP):
            rendered = False
            for attempt in range(MAX_RENDER_ATTEMPTS):
                prepare_random_orientation(objects)
                position_camera_and_light(camera, light, max_dimension)
                bpy.context.view_layer.update()
                bbox = compute_yolo_bbox(objects, camera)
                if bbox is None:
                    continue

                stem = f"{file_index:06d}_{safe_name(step_path.stem)}_{image_index + 1:04d}"
                source_image = output_root / "screw_type" / "images" / split / f"{stem}.png"
                bpy.context.scene.render.filepath = str(source_image)
                bpy.ops.render.render(write_still=True)
                if not source_image.exists():
                    continue

                x, y, width, height = bbox
                for attribute in ATTRIBUTES:
                    dataset_dir = output_root / attribute
                    image_path = dataset_dir / "images" / split / f"{stem}.png"
                    label_path = dataset_dir / "labels" / split / f"{stem}.txt"
                    if attribute != "screw_type":
                        shutil.copy2(source_image, image_path)

                    class_id = class_maps[attribute][labels[attribute]]
                    line = (
                        f"{class_id} {x:.6f} {y:.6f} "
                        f"{width:.6f} {height:.6f}\n"
                    )
                    label_path.write_text(line, encoding="utf-8")

                successful += 1
                rendered = True
                break

            if not rendered:
                log(f"WARNING: {step_path.name}, view {image_index + 1}: "
                    f"keine gültige Bounding Box nach {MAX_RENDER_ATTEMPTS} Versuchen.")

    finally:
        for obj in objects:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

    record["rendered_images"] = successful
    log(f"{step_path.name}: {successful}/{IMAGES_PER_STEP} Bilder, "
        + ", ".join(f"{k}={v}" for k, v in labels.items()))

def main():
    if not INPUT_ROOT.exists():
        raise FileNotFoundError(f"Input-Ordner nicht gefunden: {INPUT_ROOT}")

    step_files = sorted(
        p for p in INPUT_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in {".step", ".stp"}
    )
    if not step_files:
        raise RuntimeError(f"Keine .step/.stp-Dateien unter {INPUT_ROOT} gefunden.")

    overrides = load_csv_overrides(CSV_PATH, INPUT_ROOT)
    records = []
    metadata_rows = []

    log(f"{len(step_files)} STEP-Dateien gefunden.")
    for path in step_files:
        try:
            parsed = parse_filename(path)
            labels = apply_overrides_and_validate(path, INPUT_ROOT, parsed, overrides)
            records.append({"path": path, "labels": labels, "rendered_images": 0})
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            log(f"SKIP {path.name}: {message}")
            metadata_rows.append({
                "relative_path": path.relative_to(INPUT_ROOT).as_posix(),
                "filename": path.name,
                "error": message,
            })

    if not records:
        raise RuntimeError(
            "Keine STEP-Datei besitzt fünf vollständige Labels. "
            "Prüfe die Dateinamen und screw_metadata.csv."
        )

    # Build deterministic class IDs from all valid records before rendering.
    class_maps = {}
    for attribute in ATTRIBUTES:
        values = sorted({record["labels"][attribute] for record in records})
        class_maps[attribute] = {value: idx for idx, value in enumerate(values)}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = OUTPUT_ROOT / f"screw_dataset_{timestamp}"
    create_output_structure(output_root)

    split_map = make_split_map(records)
    camera, light = setup_scene()

    log(f"Ausgabeverzeichnis: {output_root}")
    log(f"Anzahl gültiger STEP-Dateien: {len(records)}")
    log(f"Bilder pro STEP: {IMAGES_PER_STEP}")
    log(f"Klassen: {class_maps}")

    for file_index, record in enumerate(records):
        split = split_map[str(record["path"])]
        try:
            render_record(record, file_index, split, class_maps, output_root, camera, light)
            metadata_rows.append({
                "relative_path": record["path"].relative_to(INPUT_ROOT).as_posix(),
                "filename": record["path"].name,
                "split": split,
                **record["labels"],
                "rendered_images": record["rendered_images"],
                "error": "",
            })
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            log(f"ERROR {record['path'].name}: {message}")
            metadata_rows.append({
                "relative_path": record["path"].relative_to(INPUT_ROOT).as_posix(),
                "filename": record["path"].name,
                "split": split,
                **record["labels"],
                "rendered_images": record.get("rendered_images", 0),
                "error": message,
            })

    write_class_files(output_root, class_maps)

    fields = [
        "relative_path", "filename", "split", "din_standard",
        *ATTRIBUTES, "rendered_images", "error"
    ]
    with (output_root / "metadata.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in metadata_rows:
            writer.writerow(row)

    log("DATENSATZ-GENERIERUNG ABGESCHLOSSEN")
    log(f"Ergebnis: {output_root}")
    for attribute, mapping in class_maps.items():
        log(f"{attribute}: {mapping}")

if __name__ == "__main__":
    main()
