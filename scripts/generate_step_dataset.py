"""Generate two YOLO datasets (head type and tool size) from Würth STEP files.
Run inside Blender with StepForge available on PYTHONPATH.
"""
from __future__ import annotations

import csv
import math
import os
import random
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

# StepForge is installed into /opt/stepforge in the Docker image.
sys.path.insert(0, "/opt")
from stepforge.core import convert_step  # noqa: E402

INPUT_ROOT = Path(os.environ.get("INPUT_DIR", "/data/input"))
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_DIR", "/data/output"))
IMAGES_PER_STEP = int(os.environ.get("IMAGES_PER_STEP", "30"))
RES_X = int(os.environ.get("RES_X", "640"))
RES_Y = int(os.environ.get("RES_Y", "640"))
DEFLECTION = float(os.environ.get("STEP_DEFLECTION", "0.025"))
TRAIN_RATIO, VAL_RATIO = 0.70, 0.20
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Standards provide a useful fallback where folder names are generic.
# Keep this table explicit and editable; do not infer unlisted standards.
DIN_HEAD_TYPE = {
    "DIN_934": "Hex_Nut",
    "DIN_961": "Hex_Head",
    "DIN_933": "Hex_Head",
    "DIN_931": "Hex_Head",
    "DIN_912": "Hex_Socket_Cap",
    "DIN_7991": "Countersunk_Hex_Socket",
    "DIN_7984": "Low_Head_Hex_Socket",
    "ISO_7380": "Button_Head_Hex_Socket",
}

# Tool/drive size is only assigned when explicitly present in the filename.
# Examples: SW8, TX25, HEX5, INBUS4. No nominal thread diameter is silently
# treated as the tool size.
TOOL_PATTERNS = [
    (re.compile(r"(?:^|[_-])(?:SW|WRENCH)[_-]?(\d+(?:[.,]\d+)?)", re.I), "SW"),
    (re.compile(r"(?:^|[_-])(?:TX|TORX)[_-]?(\d+)", re.I), "TX"),
    (re.compile(r"(?:^|[_-])(?:HEX|INBUS|ALLEN)[_-]?(\d+(?:[.,]\d+)?)", re.I), "HEX"),
]


def log(msg):
    print(f"[STEP-YOLO] {msg}", flush=True)


def clean_class(value):
    value = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")
    return value or "Unknown"


def parse_filename(path: Path):
    stem = path.stem
    upper = stem.upper()
    din_match = re.search(r"(?:^|_)DIN[_-]?(\d+[A-Z0-9]*)", upper)
    din = f"DIN_{din_match.group(1)}" if din_match else ""
    # Würth article number is normally the second token after Wuerth/Würth.
    tokens = stem.split("_")
    article = tokens[1] if len(tokens) > 1 and tokens[0].lower() in ("wuerth", "würth", "wurth") else ""
    # Preserve a likely nominal thread designation separately as metadata.
    nominal = ""
    if din_match:
        before_din = stem[:din_match.start()].rstrip("_").split("_")
        candidate = before_din[-1] if before_din else ""
        if re.fullmatch(r"\d{2,3}", candidate):
            nominal = f"M{candidate[:-1]}.{candidate[-1]}" if len(candidate) == 2 else f"M{candidate[0]}.{candidate[1:]}"
        elif re.fullmatch(r"M\d+(?:[.,]\d+)?", candidate, re.I):
            nominal = candidate.upper().replace(",", ".")
    tool_size = "Unknown"
    for pattern, prefix in TOOL_PATTERNS:
        match = pattern.search(upper)
        if match:
            tool_size = f"{prefix}{match.group(1).replace(',', '.')}"
            break
    return {"article_number": article, "din_standard": din,
            "nominal_thread_size": nominal, "tool_size": tool_size}


def classify_head_type(path: Path, meta: dict):
    # Immediate parent folder is the user's screw-family grouping.
    folder = path.parent.name
    generic = folder.lower() in {"input", "step", "steps", "stp", "data"}
    if not generic:
        return clean_class(folder)
    return DIN_HEAD_TYPE.get(meta["din_standard"], "Unknown")


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_mode = "RGB"
    world = scene.world or bpy.data.worlds.new("ScrewDatasetWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.22, 0.22, 0.22, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    cam_data = bpy.data.cameras.new("DatasetCamera")
    camera = bpy.data.objects.new("DatasetCamera", cam_data)
    scene.collection.objects.link(camera)
    camera.data.lens = 50
    camera.data.clip_start, camera.data.clip_end = 0.001, 1000
    scene.camera = camera
    light_data = bpy.data.lights.new("DatasetArea", "AREA")
    light = bpy.data.objects.new("DatasetArea", light_data)
    scene.collection.objects.link(light)
    light.data.energy, light.data.shape, light.data.size = 1200, "DISK", 4.0
    return camera, light


def aim_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def world_corners(obj):
    bpy.context.view_layer.update()
    return [obj.matrix_world @ Vector(c) for c in obj.bound_box]


def bbox_center_size(objects):
    corners = [p for obj in objects for p in world_corners(obj)]
    lo = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    hi = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    return (lo + hi) / 2, hi - lo


def yolo_bbox(objects, camera):
    scene = bpy.context.scene
    projected = [world_to_camera_view(scene, camera, p) for obj in objects for p in world_corners(obj)]
    if not projected or any(p.z <= 0 for p in projected):
        return None
    x0, x1 = min(p.x for p in projected), max(p.x for p in projected)
    y0, y1 = min(p.y for p in projected), max(p.y for p in projected)
    if x0 < 0 or y0 < 0 or x1 > 1 or y1 > 1 or x1 <= x0 or y1 <= y0:
        return None
    return ((x0 + x1) / 2, 1 - (y0 + y1) / 2, x1 - x0, y1 - y0)


def import_step_as_blender_meshes(step_path: Path):
    """Use StepForge's STEP parser/tessellator, then create Blender mesh objects.
    Solid.matrix from STEP assembly instances is already applied by convert_step.
    """
    solids = convert_step(str(step_path), deflection=DEFLECTION, keep_surfaces=False)
    objects = []
    for idx, solid in enumerate(solids):
        if not solid.mesh.verts or not solid.mesh.faces:
            continue
        mesh = bpy.data.meshes.new(f"{step_path.stem}_{idx:03d}_mesh")
        mesh.from_pydata(solid.mesh.verts, [], solid.mesh.faces)
        mesh.update()
        obj = bpy.data.objects.new(f"{clean_class(solid.name)}_{idx:03d}", mesh)
        bpy.context.scene.collection.objects.link(obj)
        mat = bpy.data.materials.get("ScrewSteel") or bpy.data.materials.new("ScrewSteel")
        mat.diffuse_color = (0.48, 0.52, 0.58, 1)
        mesh.materials.append(mat)
        objects.append(obj)
    if not objects:
        raise RuntimeError("STEP conversion produced no renderable solids")
    return objects, solids


def choose_split(index, total):
    # Split by STEP file, not by rendered image, to avoid near-identical views
    # of one screw leaking across train/validation/test.
    r = index / max(total, 1)
    return "train" if r < TRAIN_RATIO else ("val" if r < TRAIN_RATIO + VAL_RATIO else "test")


def render_one(step_path, file_index, total_files, classes, camera, light, out_root, metadata_rows):
    meta = parse_filename(step_path)
    head_type = classify_head_type(step_path, meta)
    tool_size = meta["tool_size"]
    head_id = classes["head_type"].setdefault(head_type, len(classes["head_type"]))
    size_id = classes["tool_size"].setdefault(tool_size, len(classes["tool_size"]))
    objects, solids = import_step_as_blender_meshes(step_path)
    center, size = bbox_center_size(objects)
    max_dim = max(size.x, size.y, size.z, 0.001)
    # Keep imported STEP world coordinates internally; translate the complete
    # screw only for dataset staging, never individual components.
    for obj in objects:
        obj.location -= center
    bpy.context.view_layer.update()
    split = choose_split(file_index, total_files)
    rendered = 0
    try:
        for n in range(IMAGES_PER_STEP):
            az = random.uniform(0, 2 * math.pi)
            el = math.radians(random.uniform(18, 78))
            dist = max_dim * random.uniform(2.5, 3.6)
            target = Vector((0, 0, 0))
            camera.location = (dist * math.cos(el) * math.cos(az), dist * math.cos(el) * math.sin(az), dist * math.sin(el))
            aim_at(camera, target)
            light.location = (camera.location.x * 0.8, camera.location.y * 0.8, camera.location.z * 1.2)
            aim_at(light, target)
            light.data.energy = random.uniform(700, 1600)
            bg = bpy.context.scene.world.node_tree.nodes["Background"]
            shade = random.uniform(0.12, 0.48)
            bg.inputs["Color"].default_value = (shade, shade, shade, 1)
            bpy.context.view_layer.update()
            box = yolo_bbox(objects, camera)
            if box is None:
                continue
            stem = f"{file_index:06d}_{clean_class(step_path.stem)}_{n:03d}"
            image_path = out_root / "head_type" / "images" / split / f"{stem}.png"
            bpy.context.scene.render.filepath = str(image_path)
            bpy.ops.render.render(write_still=True)
            tool_image_path = out_root / "tool_size" / "images" / split / f"{stem}.png"
            shutil.copy2(image_path, tool_image_path)
            x, y, w, h = box
            line = f"0 {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n"
            (out_root / "head_type" / "labels" / split / f"{stem}.txt").write_text(line, encoding="utf-8")
            (out_root / "tool_size" / "labels" / split / f"{stem}.txt").write_text(line, encoding="utf-8")
            rendered += 1
    finally:
        for obj in objects:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    metadata_rows.append({**meta, "step_file": str(step_path), "head_type": head_type,
                          "tool_size": tool_size, "solid_count": len(solids), "rendered_images": rendered})
    log(f"{step_path.name}: head={head_type}, tool={tool_size}, {rendered}/{IMAGES_PER_STEP} renders")


def write_dataset_config(out_root, classes):
    for attribute, class_map in classes.items():
        names = sorted(class_map, key=class_map.get)
        dataset_dir = out_root / attribute
        (dataset_dir / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
        yaml = [f"path: {dataset_dir.as_posix()}", "train: images/train", "val: images/val", "test: images/test",
                f"nc: {len(names)}", "names:"]
        yaml += [f"  {i}: '{name}'" for i, name in enumerate(names)]
        (out_root / f"data_{attribute}.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")


def main():
    if not INPUT_ROOT.exists():
        raise FileNotFoundError(f"Input directory does not exist: {INPUT_ROOT}")
    files = sorted(p for p in INPUT_ROOT.rglob("*") if p.is_file() and p.suffix.lower() in {".step", ".stp"})
    if not files:
        raise RuntimeError(f"No STEP/STP files found recursively in {INPUT_ROOT}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = OUTPUT_ROOT / f"screw_dataset_{stamp}"
    for attribute in ("head_type", "tool_size"):
        for split in ("train", "val", "test"):
            (out_root / attribute / "images" / split).mkdir(parents=True, exist_ok=True)
            (out_root / attribute / "labels" / split).mkdir(parents=True, exist_ok=True)
    camera, light = setup_scene()
    classes = {"head_type": {}, "tool_size": {}}
    rows = []
    log(f"Found {len(files)} STEP files under {INPUT_ROOT}")
    for idx, step_path in enumerate(files):
        try:
            render_one(step_path, idx, len(files), classes, camera, light, out_root, rows)
        except Exception as exc:
            log(f"ERROR {step_path}: {type(exc).__name__}: {exc}")
            rows.append({"step_file": str(step_path), "error": f"{type(exc).__name__}: {exc}"})
    write_dataset_config(out_root, classes)
    if rows:
        fields = sorted({k for row in rows for k in row})
        with (out_root / "metadata.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    log(f"Finished. Dataset: {out_root}")
    log(f"Head classes: {classes['head_type']}")
    log(f"Tool-size classes: {classes['tool_size']}")

if __name__ == "__main__":
    main()
