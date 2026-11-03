# STEP-to-YOLO screw dataset generator

Dockerized Blender 4.5 + StepForge STEP conversion. The container recursively scans `./input` for `.step` and `.stp`, converts each file to Blender mesh objects, renders randomized views and creates two YOLO label sets: screw/head family and tool/drive size.

## Input structure

Put one screw family per subfolder. Folder name becomes the `head_type` class. The script also reads the Würth-style filename for article number, DIN standard and a possible explicit tool-size token.

```text
input/
  Hexagon_Socket_Head/
    Wuerth_006410_25_DIN_961_Stahl_8.8_verzinkt_Feingewinde_LOD_High.step
  Hexagon_Nut/
    Wuerth_031760_DIN_934_Stahl_I6I__I8I_verzinkt_LOD_High.step
```

The examples above are illustrative. A STEP file can be anywhere below `input/`; the immediate parent directory is used as the head-family label. If files are directly in `input/` or in generic folders (`step`, `steps`, `stp`, `data`), a small editable DIN-to-family fallback table is used.

## Run on Windows (PowerShell)

1. Install Docker Desktop and start it.
2. Extract this project folder.
3. Put your STEP folders under `input`.
4. From this folder run:

```powershell
docker compose build
docker compose run --rm screw-dataset-generator
```

Generated data is written to `output/screw_dataset_<timestamp>/`.

## Output

- `head_type/images` and `head_type/labels`: independent YOLO dataset for head family
- `tool_size/images` and `tool_size/labels`: independent YOLO dataset for tool/drive size
- `data_head_type.yaml`, `data_tool_size.yaml`: separate YOLO configs
- `metadata.csv`: source STEP file, extracted filename fields, assigned labels, render count and errors

Each dataset contains the same rendered images and bounding boxes, with its own class ID `0` per object. Train two separate YOLO models using `data_head_type.yaml` and `data_tool_size.yaml`.

## Important: tool-size labels

The script only assigns a tool-size class when the filename explicitly contains a token such as `SW8`, `TX25`, `HEX5`, or `INBUS4`. Otherwise it labels the size as `Unknown`. A nominal thread diameter (for example a possible `M2.5` token) is stored separately in `metadata.csv` and is **not** treated as a tool size. This avoids silently creating incorrect ground truth. Add additional Würth naming patterns to `TOOL_PATTERNS` in `scripts/generate_step_dataset.py` after checking representative filenames.

The DIN fallback table is also intentionally explicit and editable. Folder names take precedence, so use meaningful class folder names such as `Hexagon_Head`, `Hexagon_Socket`, `Countersunk`, `Button_Head`, or `Hexagon_Nut`.

## Settings

Edit `docker-compose.yml` to change `IMAGES_PER_STEP`, render resolution or STEP tessellation deflection. Lower `STEP_DEFLECTION` creates finer meshes but takes longer.

## Technical notes

- Blender does not include a native STEP importer. This image uses StepForge, a pure-Python STEP reader/tessellator, and creates mesh objects in Blender from the converted solids.
- STEP assembly instance transforms are applied by StepForge before the mesh objects are created.
- The train/validation/test split is performed per STEP file, so different views of the same CAD model do not leak across splits.
- First run needs internet access to build the image (Blender download + StepForge Git clone). Subsequent runs use the locally built image.
