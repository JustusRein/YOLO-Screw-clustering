
from __future__ import annotations

import bpy
import csv
import json
import math
import os
import random
import re
import traceback

from datetime import datetime
from pathlib import Path

from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_ROOT = Path(
    os.environ.get(
        "INPUT_DIR",
        "/data/input/stl"
    )
)

METADATA_CSV = Path(
    os.environ.get(
        "METADATA_FILE",
        "/data/input/generated_metadata.csv"
    )
)

DISTRACTOR_ROOT = Path(
    os.environ.get(
        "DISTRACTOR_DIR",
        "/data/input/distractors"
    )
)

BACKGROUND_ROOT = Path(
    os.environ.get(
        "BACKGROUND_DIR",
        "/data/input/backgrounds"
    )
)

OUTPUT_ROOT = Path(
    os.environ.get(
        "OUTPUT_DIR",
        "/workspace/output"
    )
)

SCENE_COUNT = int(
    os.environ.get("SCENE_COUNT", "1000")
)

TARGET_MIN = int(
    os.environ.get("TARGET_MIN", "1")
)

TARGET_MAX = int(
    os.environ.get("TARGET_MAX", "5")
)

DISTRACTOR_MIN = int(
    os.environ.get("DISTRACTOR_MIN", "3")
)

DISTRACTOR_MAX = int(
    os.environ.get("DISTRACTOR_MAX", "10")
)

NEGATIVE_SCENE_PROBABILITY = float(
    os.environ.get(
        "NEGATIVE_SCENE_PROBABILITY",
        "0.05"
    )
)

TABLE_SIZE = float(
    os.environ.get("TABLE_SIZE", "220")
)

RES_X = int(
    os.environ.get("RES_X", "1280")
)

RES_Y = int(
    os.environ.get("RES_Y", "720")
)

RESOLUTION_PERCENTAGE = int(
    os.environ.get("RESOLUTION_PERCENTAGE", "100")
)

RANDOM_SEED = int(
    os.environ.get("RANDOM_SEED", "42")
)

CLASS_ATTRIBUTE = os.environ.get(
    "CLASS_ATTRIBUTE",
    "screw_type"
)

# Höhere Sample-Anzahl für bessere Beleuchtung
EEVEE_SAMPLES = int(
    os.environ.get("EEVEE_SAMPLES", "64")
)

CAMERA_MARGIN = 1.12

PLACEMENT_ATTEMPTS = 80

random.seed(RANDOM_SEED)


# ============================================================
# GLOBAL CACHES
# ============================================================

MATERIAL_CACHE = {}
BACKGROUND_CACHE = {}


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
                    f"Missing {CLASS_ATTRIBUTE} for {filename}"
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

    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.cameras,
        bpy.data.lights
    ):

        for datablock in list(datablocks):

            if datablock.users == 0:

                datablocks.remove(datablock)


# ============================================================
# MATERIALS
# ============================================================

def create_material(
    name,
    color,
    metallic,
    roughness
):

    material = bpy.data.materials.new(name)

    material.diffuse_color = color
    material.use_nodes = True

    bsdf = material.node_tree.nodes.get(
        "Principled BSDF"
    )

    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    return material


def initialize_materials():

    styles = {

        # ----------------------------------------------------
        # TARGET MATERIALS: SILVER AND BLACK
        # ----------------------------------------------------

        "StainlessSteel": (
            (0.68, 0.70, 0.74, 1),
            0.95,
            0.23
        ),

        "ZincPlatedSteel": (
            (0.82, 0.84, 0.87, 1),
            0.92,
            0.30
        ),

        "BlackOxideSteel": (
            (0.025, 0.030, 0.040, 1),
            0.88,
            0.30
        ),

        "DarkSteel": (
            (0.075, 0.085, 0.105, 1),
            0.90,
            0.32
        ),

        # ----------------------------------------------------
        # DISTRACTOR MATERIALS
        # ----------------------------------------------------

        "Brass": (
            (0.68, 0.43, 0.12, 1),
            0.85,
            0.30
        ),

        "Aluminium": (
            (0.58, 0.62, 0.66, 1),
            0.90,
            0.30
        ),

        "PlasticBlack": (
            (0.025, 0.03, 0.04, 1),
            0.05,
            0.42
        ),

        "PlasticBlue": (
            (0.025, 0.12, 0.35, 1),
            0.05,
            0.38
        ),

        "Rubber": (
            (0.035, 0.04, 0.045, 1),
            0.0,
            0.78
        )
    }

    for name, values in styles.items():

        color, metallic, roughness = values

        MATERIAL_CACHE[name] = create_material(
            name,
            color,
            metallic,
            roughness
        )


# ============================================================
# EDGE SHADING
# ============================================================

def apply_edge_shading(obj):

    """
    Verbessert die Darstellung geometrischer Kanten.

    Die Flächen werden geglättet.
    Kanten mit einem deutlichen Winkelunterschied
    werden durch den Edge Split Modifier getrennt.

    Weighted Normals verbessern anschließend
    die Darstellung der Oberflächen.
    """

    if obj.type != "MESH":
        return

    # --------------------------------------------------------
    # SMOOTH SHADING
    # --------------------------------------------------------

    for polygon in obj.data.polygons:

        polygon.use_smooth = True

    # --------------------------------------------------------
    # EDGE SPLIT
    # --------------------------------------------------------

    edge_split = obj.modifiers.new(
        name="SharpEdges",
        type="EDGE_SPLIT"
    )

    edge_split.use_edge_angle = True
    edge_split.use_edge_sharp = True

    edge_split.split_angle = math.radians(30)

    # --------------------------------------------------------
    # WEIGHTED NORMAL
    # --------------------------------------------------------

    weighted_normal = obj.modifiers.new(
        name="WeightedNormals",
        type="WEIGHTED_NORMAL"
    )

    weighted_normal.keep_sharp = True
    weighted_normal.weight = 50
    weighted_normal.thresh = 0.01


# ============================================================
# MATERIAL ASSIGNMENT
# ============================================================

def assign_material(obj, target=True):

    if target:

        # Schrauben und Muttern:
        # ausschließlich silberne und schwarze Materialien.

        material_names = [
            "StainlessSteel",
            "ZincPlatedSteel",
            "BlackOxideSteel",
            "DarkSteel"
        ]

    else:

        # Distraktoren:
        # bisherige zufällige Materialauswahl.

        material_names = [
            "DarkSteel",
            "Aluminium",
            "PlasticBlack",
            "PlasticBlue",
            "Rubber",
            "Brass"
        ]

    material_name = random.choice(
        material_names
    )

    material = MATERIAL_CACHE[material_name]

    obj.data.materials.clear()
    obj.data.materials.append(material)

    apply_edge_shading(obj)


# ============================================================
# SCENE SETUP
# ============================================================

def aim_at(obj, target):

    direction = target - obj.location

    obj.rotation_euler = (
        direction
        .to_track_quat("-Z", "Y")
        .to_euler()
    )


def setup_scene():

    scene = bpy.context.scene

    # --------------------------------------------------------
    # RENDER ENGINE
    # --------------------------------------------------------

    scene.render.engine = "BLENDER_EEVEE_NEXT"

    scene.eevee.taa_render_samples = EEVEE_SAMPLES

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = RESOLUTION_PERCENTAGE

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    scene.render.film_transparent = True
    scene.render.use_compositing = True

    scene.view_settings.view_transform = "AgX"

    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

    if bpy.data.worlds.get("DatasetWorld"):

        world = bpy.data.worlds["DatasetWorld"]

    else:

        world = bpy.data.worlds.new(
            "DatasetWorld"
        )

    scene.world = world
    world.use_nodes = True

    background = world.node_tree.nodes.get(
        "Background"
    )

    background.inputs["Color"].default_value = (
        0.8,
        0.8,
        0.8,
        1
    )

    background.inputs["Strength"].default_value = 0.8

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
    camera.data.clip_start = 0.01
    camera.data.clip_end = 10000

    scene.camera = camera

    # --------------------------------------------------------
    # LIGHTS
    # --------------------------------------------------------

    lights = []

    light_settings = [
        ("KeyLight", "AREA"),
        ("FillLight", "AREA"),
        ("RimLight", "AREA")
    ]

    for name, light_type in light_settings:

        light_data = bpy.data.lights.new(
            name,
            light_type
        )

        light = bpy.data.objects.new(
            name,
            light_data
        )

        scene.collection.objects.link(light)

        light.data.shape = "DISK"

        lights.append(light)

    return camera, lights


# ============================================================
# BACKGROUND IMAGE DISCOVERY
# ============================================================

def discover_backgrounds():

    """
    Sucht nach optionalen Hintergrundfotos.

    Wenn das Verzeichnis fehlt oder keine unterstützten
    Bilddateien enthält, wird eine leere Liste zurückgegeben.

    Die Datengenerierung läuft dann mit dem normalen
    Blender-World-Hintergrund weiter.
    """

    if not BACKGROUND_ROOT.exists():

        log(
            f"Background directory not found: {BACKGROUND_ROOT}. "
            "Continuing without background photos."
        )

        return []

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff"
    }

    backgrounds = sorted(
        path
        for path in BACKGROUND_ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
    )

    if not backgrounds:

        log(
            f"No background images found in {BACKGROUND_ROOT}. "
            "Continuing without background photos."
        )

        return []

    log(
        f"Found {len(backgrounds)} background images"
    )

    return backgrounds


def load_background_image(background_path):

    key = str(background_path.resolve())

    if key in BACKGROUND_CACHE:

        return BACKGROUND_CACHE[key]

    image = bpy.data.images.load(
        str(background_path),
        check_existing=True
    )

    BACKGROUND_CACHE[key] = image

    return image


# ============================================================
# COMPOSITOR
# ============================================================

def setup_compositor(background_path):

    scene = bpy.context.scene

    scene.use_nodes = True

    tree = scene.node_tree
    tree.nodes.clear()

    # --------------------------------------------------------
    # RENDERED OBJECTS
    # --------------------------------------------------------

    render_layers = tree.nodes.new(
        "CompositorNodeRLayers"
    )

    # --------------------------------------------------------
    # BACKGROUND PHOTO
    # --------------------------------------------------------

    background_image = tree.nodes.new(
        "CompositorNodeImage"
    )

    background_image.image = load_background_image(
        background_path
    )

    scale = tree.nodes.new(
        "CompositorNodeScale"
    )

    scale.space = "RENDER_SIZE"
    scale.frame_method = "CROP"

    # --------------------------------------------------------
    # ALPHA OVER
    # --------------------------------------------------------

    alpha_over = tree.nodes.new(
        "CompositorNodeAlphaOver"
    )

    alpha_over.inputs[0].default_value = 1.0

    composite = tree.nodes.new(
        "CompositorNodeComposite"
    )

    # Photo scaled to render dimensions.
    tree.links.new(
        background_image.outputs["Image"],
        scale.inputs["Image"]
    )

    # Photo as background.
    tree.links.new(
        scale.outputs["Image"],
        alpha_over.inputs[1]
    )

    # Rendered objects as foreground.
    tree.links.new(
        render_layers.outputs["Image"],
        alpha_over.inputs[2]
    )

    tree.links.new(
        alpha_over.outputs["Image"],
        composite.inputs["Image"]
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
            f"No mesh imported from {stl_path}"
        )

    bpy.ops.object.select_all(
        action="DESELECT"
    )

    for obj in imported:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = imported[0]

    if len(imported) > 1:
        bpy.ops.object.join()

    obj = bpy.context.view_layer.objects.active

    bpy.ops.object.origin_set(
        type="ORIGIN_GEOMETRY",
        center="BOUNDS"
    )

    return obj


# ============================================================
# OBJECT BOUNDS
# ============================================================

def world_corners(obj):

    bpy.context.view_layer.update()

    return [
        obj.matrix_world @ Vector(corner)
        for corner in obj.bound_box
    ]


def object_bounds(obj):

    corners = world_corners(obj)

    minimum = Vector((
        min(point.x for point in corners),
        min(point.y for point in corners),
        min(point.z for point in corners)
    ))

    maximum = Vector((
        max(point.x for point in corners),
        max(point.y for point in corners),
        max(point.z for point in corners)
    ))

    return minimum, maximum


# ============================================================
# INSTANCE PLACEMENT
# ============================================================

def prepare_instance(
    obj,
    target,
    occupied
):

    # --------------------------------------------------------
    # SCALE
    # --------------------------------------------------------

    scale = random.uniform(
        0.85,
        1.15
    )

    obj.scale = (
        scale,
        scale,
        scale
    )

    # --------------------------------------------------------
    # ROTATION
    # --------------------------------------------------------

    if random.random() < 0.75:

        obj.rotation_euler = (
            math.radians(random.uniform(-12, 12)),
            math.radians(random.uniform(-12, 12)),
            math.radians(random.uniform(0, 360))
        )

    else:

        obj.rotation_euler = (
            math.radians(random.uniform(-75, 75)),
            math.radians(random.uniform(-75, 75)),
            math.radians(random.uniform(0, 360))
        )

    obj.location = (0, 0, 0)

    bpy.context.view_layer.update()

    minimum, maximum = object_bounds(obj)

    dimensions = maximum - minimum

    radius = max(
        dimensions.x,
        dimensions.y,
        1.0
    ) * 0.5

    # --------------------------------------------------------
    # POSITION
    # --------------------------------------------------------

    half_size = TABLE_SIZE * 0.40

    selected_position = None

    for attempt in range(PLACEMENT_ATTEMPTS):

        x = random.uniform(
            -half_size,
            half_size
        )

        y = random.uniform(
            -half_size,
            half_size
        )

        valid = True

        for other_x, other_y, other_radius in occupied:

            distance = math.sqrt(
                (x - other_x) ** 2
                + (y - other_y) ** 2
            )

            minimum_distance = (
                radius + other_radius
            ) * random.uniform(0.55, 0.85)

            if distance < minimum_distance:

                valid = False
                break

        if valid:

            selected_position = (
                x,
                y
            )

            break

    if selected_position is None:

        selected_position = (
            random.uniform(-half_size, half_size),
            random.uniform(-half_size, half_size)
        )

    x, y = selected_position

    obj.location.x = x
    obj.location.y = y

    bpy.context.view_layer.update()

    minimum, maximum = object_bounds(obj)

    # Place object on the virtual surface.
    obj.location.z -= minimum.z

    bpy.context.view_layer.update()

    occupied.append(
        (x, y, radius)
    )

    assign_material(
        obj,
        target=target
    )

    return obj


# ============================================================
# CAMERA RANDOMIZATION
# ============================================================

def randomize_camera(
    camera,
    lights
):

    azimuth = random.uniform(
        0,
        2 * math.pi
    )

    elevation = math.radians(
        random.uniform(48, 78)
    )

    distance = TABLE_SIZE * 2.5

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

    camera.data.ortho_scale = (
        TABLE_SIZE * CAMERA_MARGIN
    )

    # --------------------------------------------------------
    # LIGHTING
    # --------------------------------------------------------

    light_directions = [
        Vector((1, -1, 2)),
        Vector((-1, 1, 1.5)),
        Vector((0.5, 1, 2))
    ]

    for index, light in enumerate(lights):

        direction = light_directions[index].copy()

        direction.rotate(
            camera.rotation_euler.to_quaternion()
        )

        direction.normalize()

        light.location = (
            direction * TABLE_SIZE * 0.9
        )

        aim_at(
            light,
            Vector((0, 0, 0))
        )

        light.data.energy = random.uniform(
            700,
            1800
        )

        # Kleinere Lichtquellen für deutlichere
        # Licht- und Schattenübergänge.
        light.data.size = random.uniform(
            1.5,
            4.5
        )

    bpy.context.view_layer.update()


# ============================================================
# YOLO BOUNDING BOX
# ============================================================

def calculate_yolo_bbox(
    obj,
    camera
):

    scene = bpy.context.scene

    projected = [
        world_to_camera_view(
            scene,
            camera,
            point
        )
        for point in world_corners(obj)
    ]

    if not projected:
        return None

    if any(
        point.z <= 0
        for point in projected
    ):
        return None

    x_min = max(
        0.0,
        min(point.x for point in projected)
    )

    x_max = min(
        1.0,
        max(point.x for point in projected)
    )

    y_min = max(
        0.0,
        min(point.y for point in projected)
    )

    y_max = min(
        1.0,
        max(point.y for point in projected)
    )

    if (
        x_max <= x_min
        or y_max <= y_min
    ):
        return None

    x_center = (
        x_min + x_max
    ) / 2.0

    y_center = 1.0 - (
        y_min + y_max
    ) / 2.0

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
# DISCOVER TARGET MODELS
# ============================================================

def discover_target_models():

    if not INPUT_ROOT.exists():

        raise FileNotFoundError(
            f"Fastener directory not found: {INPUT_ROOT}"
        )

    metadata = load_metadata(
        METADATA_CSV
    )

    stl_files = sorted(
        path
        for path in INPUT_ROOT.rglob("*.stl")
        if path.is_file()
    )

    models = []
    errors = []

    for stl_path in stl_files:

        entry = metadata.get(
            stl_path.name
        )

        if entry is None:

            errors.append({
                "file": str(stl_path),
                "error": "No matching metadata entry"
            })

            continue

        models.append({
            "path": stl_path,
            "class_name": entry["class_name"],
            "class_value": entry["class_value"]
        })

    if not models:

        raise RuntimeError(
            "No target STL models matched the metadata CSV."
        )

    return models, errors


# ============================================================
# DISCOVER DISTRACTOR MODELS
# ============================================================

def discover_distractors():

    if not DISTRACTOR_ROOT.exists():

        log(
            "WARNING: Distractor directory does not exist."
        )

        return []

    distractors = sorted(
        path
        for path in DISTRACTOR_ROOT.rglob("*.stl")
        if path.is_file()
    )

    log(
        f"Found {len(distractors)} distractor STL files"
    )

    return distractors


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

    (output_root / "classes.txt").write_text(
        "\n".join(class_names) + "\n",
        encoding="utf-8"
    )

    (output_root / "class_mapping.json").write_text(
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
# CREATE SCENE INSTANCES
# ============================================================

def create_target_instances(
    target_models,
    class_ids,
    occupied
):

    count = random.randint(
        TARGET_MIN,
        TARGET_MAX
    )

    instances = []

    for _ in range(count):

        model = random.choice(
            target_models
        )

        obj = import_stl(
            model["path"]
        )

        prepare_instance(
            obj,
            target=True,
            occupied=occupied
        )

        instances.append({
            "object": obj,
            "class_name": model["class_name"],
            "class_id": class_ids[
                model["class_name"]
            ],
            "source_file": model["path"].name
        })

    return instances


def create_distractor_instances(
    distractor_models,
    occupied
):

    if not distractor_models:
        return []

    count = random.randint(
        DISTRACTOR_MIN,
        DISTRACTOR_MAX
    )

    instances = []

    for _ in range(count):

        stl_path = random.choice(
            distractor_models
        )

        try:

            obj = import_stl(
                stl_path
            )

            prepare_instance(
                obj,
                target=False,
                occupied=occupied
            )

            instances.append({
                "object": obj,
                "source_file": stl_path.name
            })

        except Exception as error:

            log(
                f"Could not import distractor "
                f"{stl_path.name}: {error}"
            )

    return instances


# ============================================================
# REMOVE SCENE OBJECTS
# ============================================================

def remove_instance_objects(
    target_instances,
    distractor_instances
):

    objects = []

    for instance in target_instances:
        objects.append(instance["object"])

    for instance in distractor_instances:
        objects.append(instance["object"])

    for obj in objects:

        if obj.name not in bpy.data.objects:
            continue

        mesh = (
            obj.data
            if obj.type == "MESH"
            else None
        )

        bpy.data.objects.remove(
            obj,
            do_unlink=True
        )

        if mesh is not None and mesh.users == 0:

            bpy.data.meshes.remove(mesh)


# ============================================================
# RENDER SCENE
# ============================================================

def render_scene(
    scene_index,
    target_models,
    distractor_models,
    background_models,
    class_ids,
    output_root
):

    clear_scene()

    camera, lights = setup_scene()

    # --------------------------------------------------------
    # OPTIONAL BACKGROUND PHOTO
    # --------------------------------------------------------

    if background_models:

        background_path = random.choice(
            background_models
        )

        setup_compositor(
            background_path
        )

        log(
            f"Using background photo: {background_path.name}"
        )

    else:

        background_path = None

        # No photo: disable the compositor and render
        # the scene with the normal Blender World background.
        bpy.context.scene.use_nodes = False
        bpy.context.scene.render.film_transparent = False

    occupied = []

    target_instances = []
    distractor_instances = []

    negative_scene = (
        random.random()
        < NEGATIVE_SCENE_PROBABILITY
    )

    try:

        # ----------------------------------------------------
        # TARGET OBJECTS
        # ----------------------------------------------------

        if not negative_scene:

            target_instances = create_target_instances(
                target_models,
                class_ids,
                occupied
            )

        # ----------------------------------------------------
        # UNLABELED DISTRACTORS
        # ----------------------------------------------------

        distractor_instances = create_distractor_instances(
            distractor_models,
            occupied
        )

        # ----------------------------------------------------
        # CAMERA AND LIGHTS
        # ----------------------------------------------------

        randomize_camera(
            camera,
            lights
        )

        # ----------------------------------------------------
        # YOLO LABELS
        # ----------------------------------------------------

        label_lines = []
        visible_targets = []

        for instance in target_instances:

            bbox = calculate_yolo_bbox(
                instance["object"],
                camera
            )

            if bbox is None:
                continue

            class_id = instance["class_id"]

            x, y, width, height = bbox

            label_lines.append(
                f"{class_id} "
                f"{x:.6f} "
                f"{y:.6f} "
                f"{width:.6f} "
                f"{height:.6f}"
            )

            visible_targets.append(instance)

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        filename = (
            f"scene_{scene_index:06d}.png"
        )

        image_path = (
            output_root
            / "images"
            / filename
        )

        label_path = (
            output_root
            / "labels"
            / f"scene_{scene_index:06d}.txt"
        )

        bpy.context.scene.render.filepath = str(
            image_path
        )

        bpy.ops.render.render(
            write_still=True
        )

        # Empty file = negative image.
        label_path.write_text(
            "\n".join(label_lines),
            encoding="utf-8"
        )

        return {
            "scene": filename,
            "status": "success",
            "negative_scene": negative_scene,
            "background": (
                background_path.name
                if background_path is not None
                else ""
            ),
            "target_instances": len(target_instances),
            "visible_targets": len(visible_targets),
            "distractor_instances": len(distractor_instances),
            "labels": len(label_lines),
            "target_files": ";".join(
                instance["source_file"]
                for instance in target_instances
            ),
            "distractor_files": ";".join(
                instance["source_file"]
                for instance in distractor_instances
            ),
            "error": ""
        }

    finally:

        remove_instance_objects(
            target_instances,
            distractor_instances
        )


# ============================================================
# MAIN
# ============================================================

def main():

    log("========================================")
    log("MULTI-OBJECT DATASET GENERATION")
    log("========================================")

    log(f"Scenes: {SCENE_COUNT}")
    log(f"Target objects: {TARGET_MIN}-{TARGET_MAX}")
    log(f"Distractors: {DISTRACTOR_MIN}-{DISTRACTOR_MAX}")
    log(f"Negative probability: {NEGATIVE_SCENE_PROBABILITY}")
    log(f"Resolution: {RES_X}x{RES_Y}")
    log(f"Engine: Eevee")
    log(f"Eevee samples: {EEVEE_SAMPLES}")

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    target_models, input_errors = discover_target_models()

    distractor_models = discover_distractors()

    background_models = discover_backgrounds()

    class_names = sorted({
        model["class_name"]
        for model in target_models
    })

    class_ids = {
        name: index
        for index, name in enumerate(class_names)
    }

    log(
        f"Target STL models: {len(target_models)}"
    )

    log(
        f"Classes: {class_ids}"
    )

    log(
        f"Distractor STL models: {len(distractor_models)}"
    )

    log(
        f"Background images: {len(background_models)}"
    )

    if not background_models:

        log(
            "No background photos available. "
            "Scenes will be rendered without photo backgrounds."
        )

    if not distractor_models:

        log(
            "WARNING: No distractors found. "
            "Scenes will contain only target objects."
        )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_root = (
        OUTPUT_ROOT
        / f"multi_object_dataset_{stamp}"
    )

    create_output_structure(
        output_root
    )

    write_class_configuration(
        output_root,
        class_ids
    )

    # --------------------------------------------------------
    # INITIALIZE MATERIALS
    # --------------------------------------------------------

    initialize_materials()

    metadata_rows = []

    # --------------------------------------------------------
    # GENERATION
    # --------------------------------------------------------

    for scene_index in range(SCENE_COUNT):

        log(
            f"Generating scene "
            f"{scene_index + 1}/{SCENE_COUNT}"
        )

        try:

            result = render_scene(
                scene_index=scene_index,
                target_models=target_models,
                distractor_models=distractor_models,
                background_models=background_models,
                class_ids=class_ids,
                output_root=output_root
            )

            metadata_rows.append(result)

            log(
                f"Scene {scene_index}: "
                f"{result['target_instances']} targets, "
                f"{result['distractor_instances']} distractors, "
                f"{result['labels']} labels, "
                f"background={result['background'] or 'none'}"
            )

        except Exception as error:

            log(
                f"ERROR in scene {scene_index}: {error}"
            )

            log(
                traceback.format_exc()
            )

            metadata_rows.append({
                "scene": f"scene_{scene_index:06d}.png",
                "status": "error",
                "negative_scene": False,
                "background": "",
                "target_instances": 0,
                "visible_targets": 0,
                "distractor_instances": 0,
                "labels": 0,
                "target_files": "",
                "distractor_files": "",
                "error": str(error)
            })

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    metadata_path = (
        output_root / "metadata.csv"
    )

    fields = [
        "scene",
        "status",
        "negative_scene",
        "background",
        "target_instances",
        "visible_targets",
        "distractor_instances",
        "labels",
        "target_files",
        "distractor_files",
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

    if input_errors:

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
                    "file",
                    "error"
                ]
            )

            writer.writeheader()
            writer.writerows(input_errors)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    successful = sum(
        1
        for row in metadata_rows
        if row["status"] == "success"
    )

    negative = sum(
        1
        for row in metadata_rows
        if row.get("negative_scene")
    )

    total_targets = sum(
        row.get("target_instances", 0)
        for row in metadata_rows
    )

    total_distractors = sum(
        row.get("distractor_instances", 0)
        for row in metadata_rows
    )

    total_labels = sum(
        row.get("labels", 0)
        for row in metadata_rows
    )

    log("========================================")
    log("GENERATION FINISHED")
    log("========================================")

    log(
        f"Successful scenes: {successful}/{SCENE_COUNT}"
    )

    log(
        f"Negative scenes: {negative}"
    )

    log(
        f"Target instances: {total_targets}"
    )

    log(
        f"Unlabeled distractors: {total_distractors}"
    )

    log(
        f"YOLO labels: {total_labels}"
    )

    log(
        f"Output: {output_root}"
    )


# ============================================================
# EXECUTION
# ============================================================

main()
