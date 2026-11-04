
from __future__ import annotations

import bpy
import csv
import json
import math
import os
import random
import re

from datetime import datetime
from pathlib import Path

from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_ROOT = Path(
    os.environ.get("INPUT_DIR", "/data/input/stl")
)

METADATA_CSV = Path(
    os.environ.get(
        "METADATA_FILE",
        "/data/input/generated_metadata.csv"
    )
)

OUTPUT_ROOT = Path(
    os.environ.get("OUTPUT_DIR", "/workspace/output")
)

# Number of images generated per STL model
IMAGES_PER_MODEL = int(
    os.environ.get("IMAGES_PER_MODEL", "100")
)

# Image resolution
RES_X = int(os.environ.get("RES_X", "1024"))
RES_Y = int(os.environ.get("RES_Y", "1024"))

# Random seed
RANDOM_SEED = int(
    os.environ.get("RANDOM_SEED", "42")
)

# Metadata column used as YOLO class
CLASS_ATTRIBUTE = os.environ.get(
    "CLASS_ATTRIBUTE",
    "screw_type"
)

# Rendering
CYCLES_SAMPLES = int(
    os.environ.get("CYCLES_SAMPLES", "64")
)

# Camera framing margin
CAMERA_MARGIN = 1.35

random.seed(RANDOM_SEED)


# ============================================================
# LOGGING
# ============================================================

def log(message):

    print(
        f"[IMAGE-GENERATION] {message}",
        flush=True
    )


# ============================================================
# METADATA
# ============================================================

def clean_class_name(value):

    value = str(value).strip()

    value = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value
    )

    return value.strip("_")


def load_metadata(csv_path):

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

        required = {
            "stl_file",
            CLASS_ATTRIBUTE
        }

        missing = required - set(
            reader.fieldnames or []
        )

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

            class_value = row[
                CLASS_ATTRIBUTE
            ].strip()

            if not class_value:

                raise ValueError(
                    f"Missing {CLASS_ATTRIBUTE} "
                    f"for {filename}"
                )

            if filename in metadata:

                raise ValueError(
                    f"Duplicate metadata entry: {filename}"
                )

            metadata[filename] = {
                "class_name": clean_class_name(
                    class_value
                ),
                "class_value": class_value,
                "metadata": row
            }

    return metadata


# ============================================================
# SCENE CLEANUP
# ============================================================

def clear_scene():

    bpy.ops.object.select_all(
        action="SELECT"
    )

    bpy.ops.object.delete(
        use_global=False
    )


# ============================================================
# SCENE SETUP
# ============================================================

def setup_scene():

    scene = bpy.context.scene

    # --------------------------------------------------------
    # RENDER SETTINGS
    # --------------------------------------------------------

    scene.render.engine = "CYCLES"

    scene.cycles.samples = CYCLES_SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.device = "CPU"

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15

    # Transparent background
    scene.render.film_transparent = True

    scene.view_settings.view_transform = "AgX"

    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

    world = bpy.data.worlds.get(
        "ScrewStudioWorld"
    )

    if world is None:

        world = bpy.data.worlds.new(
            "ScrewStudioWorld"
        )

    scene.world = world
    world.use_nodes = True

    background = world.node_tree.nodes.get(
        "Background"
    )

    # World is not visible in the rendered background.
    # It only provides a weak ambient contribution.
    background.inputs["Color"].default_value = (
        0.32, 0.34, 0.38, 1
    )

    background.inputs["Strength"].default_value = 0.15

    # --------------------------------------------------------
    # CAMERA
    # --------------------------------------------------------

    camera_data = bpy.data.cameras.new(
        "DatasetCamera"
    )

    camera = bpy.data.objects.new(
        "DatasetCamera",
        camera_data
    )

    scene.collection.objects.link(camera)

    camera.data.type = "ORTHO"
    camera.data.clip_start = 0.001
    camera.data.clip_end = 10000

    scene.camera = camera

    # --------------------------------------------------------
    # THREE-POINT LIGHTING
    # --------------------------------------------------------

    lights = []

    light_settings = [
        ("KeyLight", 1800, 5.0),
        ("FillLight", 900, 4.0),
        ("RimLight", 1400, 3.0)
    ]

    for name, energy, size in light_settings:

        light_data = bpy.data.lights.new(
            name,
            "AREA"
        )

        light = bpy.data.objects.new(
            name,
            light_data
        )

        scene.collection.objects.link(light)

        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size

        lights.append(light)

    return camera, lights


# ============================================================
# CAMERA ORIENTATION
# ============================================================

def aim_at(obj, target):

    direction = target - obj.location

    obj.rotation_euler = (
        direction
        .to_track_quat("-Z", "Y")
        .to_euler()
    )


# ============================================================
# STL IMPORT
# ============================================================

def import_stl(stl_path):

    before = set(
        bpy.data.objects
    )

    bpy.ops.wm.stl_import(
        filepath=str(stl_path)
    )

    imported = [
        obj
        for obj in bpy.data.objects
        if obj not in before
        and obj.type == "MESH"
    ]

    if not imported:

        raise RuntimeError(
            f"No mesh imported from {stl_path.name}"
        )

    return imported


# ============================================================
# GEOMETRY
# ============================================================

def world_corners(obj):

    bpy.context.view_layer.update()

    return [
        obj.matrix_world @ Vector(corner)
        for corner in obj.bound_box
    ]


def get_assembly_bounds(objects):

    corners = [
        point
        for obj in objects
        for point in world_corners(obj)
    ]

    if not corners:

        raise RuntimeError(
            "Could not calculate geometry bounds"
        )

    minimum = Vector((
        min(p.x for p in corners),
        min(p.y for p in corners),
        min(p.z for p in corners)
    ))

    maximum = Vector((
        max(p.x for p in corners),
        max(p.y for p in corners),
        max(p.z for p in corners)
    ))

    center = (minimum + maximum) / 2
    size = maximum - minimum

    return center, size


def center_objects(objects, center):

    for obj in objects:

        obj.location -= center

    bpy.context.view_layer.update()


# ============================================================
# MATERIALS
# ============================================================

def assign_material(objects):

    material_styles = [

        {
            "name": "StainlessSteel",
            "color": (0.58, 0.62, 0.68, 1),
            "metallic": 0.95,
            "roughness": 0.26
        },

        {
            "name": "ZincPlatedSteel",
            "color": (0.72, 0.75, 0.79, 1),
            "metallic": 0.88,
            "roughness": 0.34
        },

        {
            "name": "BlackOxideSteel",
            "color": (0.055, 0.065, 0.08, 1),
            "metallic": 0.82,
            "roughness": 0.38
        }
    ]

    style = random.choice(
        material_styles
    )

    material = bpy.data.materials.new(
        "Mat_" + style["name"]
    )

    material.use_nodes = True

    bsdf = material.node_tree.nodes.get(
        "Principled BSDF"
    )

    bsdf.inputs["Base Color"].default_value = (
        style["color"]
    )

    bsdf.inputs["Metallic"].default_value = (
        style["metallic"]
    )

    bsdf.inputs["Roughness"].default_value = (
        style["roughness"]
        + random.uniform(-0.04, 0.04)
    )

    for obj in objects:

        obj.data.materials.clear()
        obj.data.materials.append(material)

        for polygon in obj.data.polygons:

            polygon.use_smooth = True

        modifier = obj.modifiers.new(
            "WeightedNormals",
            "WEIGHTED_NORMAL"
        )

        modifier.keep_sharp = True
        modifier.weight = 40

    return style["name"]


# ============================================================
# CAMERA RANDOMIZATION
# ============================================================

def randomize_camera(
    camera,
    lights,
    max_dimension,
    diagonal
):

    azimuth = random.uniform(
        0,
        2 * math.pi
    )

    elevation = math.radians(
        random.uniform(15, 85)
    )

    distance = max(
        diagonal * 3.0,
        max_dimension * 4.0,
        1.0
    )

    camera.location = (
        distance
        * math.cos(elevation)
        * math.cos(azimuth),

        distance
        * math.cos(elevation)
        * math.sin(azimuth),

        distance
        * math.sin(elevation)
    )

    aim_at(
        camera,
        Vector((0, 0, 0))
    )

    # Orthographic camera:
    # The complete bounding sphere remains inside the image.
    camera.data.ortho_scale = (
        diagonal * CAMERA_MARGIN
    )

    # Randomized three-point lighting
    camera_direction = camera.location.normalized()

    light_positions = [

        camera_direction
        + Vector((1, 1, 1)),

        camera_direction
        + Vector((-1, -1, 0.3)),

        -camera_direction
        + Vector((0, 1, 1))
    ]

    for index, light in enumerate(lights):

        direction = light_positions[
            index
        ].normalized()

        light.location = (
            direction * max_dimension * 2.5
        )

        aim_at(
            light,
            Vector((0, 0, 0))
        )

        light.data.energy = random.uniform(
            650,
            1800
        )

        light.data.size = random.uniform(
            2.0,
            5.0
        )

    bpy.context.view_layer.update()


# ============================================================
# YOLO BOUNDING BOX
# ============================================================

def calculate_yolo_bbox(objects, camera):

    scene = bpy.context.scene

    projected = [

        world_to_camera_view(
            scene,
            camera,
            point
        )

        for obj in objects
        for point in world_corners(obj)
    ]

    if not projected:
        return None

    if any(
        point.z <= 0
        for point in projected
    ):
        return None

    x_min = min(
        point.x for point in projected
    )

    x_max = max(
        point.x for point in projected
    )

    y_min = min(
        point.y for point in projected
    )

    y_max = max(
        point.y for point in projected
    )

    if (
        x_min < 0
        or y_min < 0
        or x_max > 1
        or y_max > 1
        or x_max <= x_min
        or y_max <= y_min
    ):
        return None

    x_center = (
        x_min + x_max
    ) / 2

    y_center = 1 - (
        y_min + y_max
    ) / 2

    width = x_max - x_min
    height = y_max - y_min

    return (
        x_center,
        y_center,
        width,
        height
    )


# ============================================================
# OUTPUT STRUCTURE
# ============================================================

def create_output_structure(output_root):

    (output_root / "images").mkdir(
        parents=True,
        exist_ok=True
    )

    (output_root / "labels").mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# RENDER ONE MODEL
# ============================================================

def render_model(
    stl_path,
    class_id,
    class_name,
    model_index,
    camera,
    lights,
    output_root
):

    log(
        f"Importing {stl_path.name}"
    )

    objects = import_stl(stl_path)

    try:

        # ----------------------------------------------------
        # GEOMETRY
        # ----------------------------------------------------

        center, size = get_assembly_bounds(
            objects
        )

        center_objects(
            objects,
            center
        )

        max_dimension = max(
            size.x,
            size.y,
            size.z,
            0.001
        )

        diagonal = max(
            size.length,
            0.001
        )

        # ----------------------------------------------------
        # MATERIAL
        # ----------------------------------------------------

        material_name = assign_material(
            objects
        )

        # ----------------------------------------------------
        # OUTPUT DIRECTORIES
        # ----------------------------------------------------

        image_dir = (
            output_root
            / "images"
            / class_name
        )

        label_dir = (
            output_root
            / "labels"
            / class_name
        )

        image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        label_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        rendered = 0
        attempts = 0

        # Allow additional attempts if a view is invalid.
        max_attempts = IMAGES_PER_MODEL * 3

        # ----------------------------------------------------
        # GENERATE IMAGES
        # ----------------------------------------------------

        while (
            rendered < IMAGES_PER_MODEL
            and attempts < max_attempts
        ):

            attempts += 1

            randomize_camera(
                camera,
                lights,
                max_dimension,
                diagonal
            )

            bbox = calculate_yolo_bbox(
                objects,
                camera
            )

            if bbox is None:
                continue

            filename = (
                f"{model_index:05d}_"
                f"{stl_path.stem}_"
                f"{rendered:05d}.png"
            )

            image_path = (
                image_dir / filename
            )

            label_path = (
                label_dir
                / f"{Path(filename).stem}.txt"
            )

            # ------------------------------------------------
            # RENDER TRANSPARENT PNG
            # ------------------------------------------------

            bpy.context.scene.render.filepath = str(
                image_path
            )

            bpy.ops.render.render(
                write_still=True
            )

            # ------------------------------------------------
            # YOLO LABEL
            # ------------------------------------------------

            x, y, width, height = bbox

            label_line = (
                f"{class_id} "
                f"{x:.6f} "
                f"{y:.6f} "
                f"{width:.6f} "
                f"{height:.6f}\n"
            )

            label_path.write_text(
                label_line,
                encoding="utf-8"
            )

            rendered += 1

            if rendered % 10 == 0:

                log(
                    f"{stl_path.name}: "
                    f"{rendered}/{IMAGES_PER_MODEL}"
                )

        log(
            f"{stl_path.name}: "
            f"{rendered}/{IMAGES_PER_MODEL} images "
            f"(material: {material_name})"
        )

        return {
            "status": (
                "success"
                if rendered == IMAGES_PER_MODEL
                else "incomplete"
            ),
            "class_id": class_id,
            "class_name": class_name,
            "rendered_images": rendered,
            "attempts": attempts,
            "material": material_name,
            "solid_count": len(objects),
            "error": (
                ""
                if rendered == IMAGES_PER_MODEL
                else "Could not generate requested number of valid views"
            )
        }

    finally:

        # ----------------------------------------------------
        # REMOVE IMPORTED GEOMETRY
        # ----------------------------------------------------

        for obj in objects:

            mesh = obj.data

            bpy.data.objects.remove(
                obj,
                do_unlink=True
            )

            if mesh.users == 0:

                bpy.data.meshes.remove(
                    mesh
                )


# ============================================================
# CLASS CONFIGURATION
# ============================================================

def write_class_configuration(
    output_root,
    class_ids
):

    class_names = sorted(
        class_ids,
        key=class_ids.get
    )

    classes_path = (
        output_root / "classes.txt"
    )

    classes_path.write_text(
        "\n".join(class_names) + "\n",
        encoding="utf-8"
    )

    mapping_path = (
        output_root / "class_mapping.json"
    )

    mapping_path.write_text(
        json.dumps(
            {
                name: class_ids[name]
                for name in class_names
            },
            indent=4
        ),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    log("Starting Blender image generation")

    log(
        f"Class attribute: {CLASS_ATTRIBUTE}"
    )

    log(
        f"Images per STL model: {IMAGES_PER_MODEL}"
    )

    log(
        f"Resolution: {RES_X} x {RES_Y}"
    )

    # --------------------------------------------------------
    # CHECK INPUT
    # --------------------------------------------------------

    if not INPUT_ROOT.exists():

        raise FileNotFoundError(
            f"STL input directory not found: {INPUT_ROOT}"
        )

    if not METADATA_CSV.exists():

        raise FileNotFoundError(
            f"Metadata CSV not found: {METADATA_CSV}"
        )

    stl_files = sorted(
        path
        for path in INPUT_ROOT.glob("*.stl")
        if path.is_file()
    )

    if not stl_files:

        raise RuntimeError(
            f"No STL files found in {INPUT_ROOT}"
        )

    metadata = load_metadata(
        METADATA_CSV
    )

    # --------------------------------------------------------
    # MATCH STL AND METADATA
    # --------------------------------------------------------

    valid_models = []
    error_rows = []

    for stl_path in stl_files:

        entry = metadata.get(
            stl_path.name
        )

        if entry is None:

            error_rows.append({
                "stl_file": stl_path.name,
                "status": "error",
                "error": "No matching metadata entry"
            })

            continue

        valid_models.append(
            (stl_path, entry)
        )

    if not valid_models:

        raise RuntimeError(
            "No STL files could be matched with metadata."
        )

    # --------------------------------------------------------
    # CLASS IDS
    # --------------------------------------------------------

    class_names = sorted({
        entry["class_name"]
        for _, entry in valid_models
    })

    class_ids = {
        name: index
        for index, name in enumerate(class_names)
    }

    # --------------------------------------------------------
    # OUTPUT DIRECTORY
    # --------------------------------------------------------

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_root = (
        OUTPUT_ROOT
        / f"screw_dataset_{stamp}"
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True
    )

    create_output_structure(
        output_root
    )

    # --------------------------------------------------------
    # SCENE
    # --------------------------------------------------------

    clear_scene()

    camera, lights = setup_scene()

    # --------------------------------------------------------
    # GENERATION
    # --------------------------------------------------------

    metadata_rows = []

    log(
        f"Found {len(valid_models)} valid STL models"
    )

    log(
        f"Found {len(class_names)} classes: {class_names}"
    )

    for index, (stl_path, entry) in enumerate(
        valid_models
    ):

        class_name = entry["class_name"]

        class_id = class_ids[class_name]

        log(
            f"Generating model {index + 1}/"
            f"{len(valid_models)}: {stl_path.name}"
        )

        try:

            result = render_model(
                stl_path=stl_path,
                class_id=class_id,
                class_name=class_name,
                model_index=index,
                camera=camera,
                lights=lights,
                output_root=output_root
            )

            metadata_rows.append({
                "stl_file": stl_path.name,
                "class_attribute": CLASS_ATTRIBUTE,
                "class_name": class_name,
                "class_id": class_id,
                **result
            })

        except Exception as error:

            log(
                f"ERROR {stl_path.name}: {error}"
            )

            metadata_rows.append({
                "stl_file": stl_path.name,
                "class_attribute": CLASS_ATTRIBUTE,
                "class_name": class_name,
                "class_id": class_id,
                "status": "error",
                "rendered_images": 0,
                "attempts": 0,
                "material": "",
                "solid_count": 0,
                "error": str(error)
            })

    # --------------------------------------------------------
    # CLASS CONFIGURATION
    # --------------------------------------------------------

    write_class_configuration(
        output_root,
        class_ids
    )

    # --------------------------------------------------------
    # GENERATION METADATA
    # --------------------------------------------------------

    metadata_path = (
        output_root / "metadata.csv"
    )

    fields = [
        "stl_file",
        "class_attribute",
        "class_name",
        "class_id",
        "status",
        "rendered_images",
        "attempts",
        "material",
        "solid_count",
        "error"
    ]

    with metadata_path.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(metadata_rows)

    # --------------------------------------------------------
    # INPUT ERRORS
    # --------------------------------------------------------

    if error_rows:

        with (
            output_root / "input_errors.csv"
        ).open(
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "stl_file",
                    "status",
                    "error"
                ]
            )

            writer.writeheader()
            writer.writerows(error_rows)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    total_images = sum(
        row.get("rendered_images", 0)
        for row in metadata_rows
    )

    successful_models = sum(
        1
        for row in metadata_rows
        if row.get("status") == "success"
    )

    log("====================================")
    log("IMAGE GENERATION FINISHED")
    log("====================================")

    log(
        f"Input STL files: {len(stl_files)}"
    )

    log(
        f"Matched models: {len(valid_models)}"
    )

    log(
        f"Successful models: {successful_models}"
    )

    log(
        f"Generated images: {total_images}"
    )

    log(
        f"Output directory: {output_root}"
    )

    log(
        f"Class mapping: {class_ids}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
