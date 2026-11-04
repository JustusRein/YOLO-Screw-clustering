# YOLO Screw Clustering

A Docker-based pipeline for generating synthetic datasets of screws, nuts, and other fasteners and training YOLO object detection models.

The project combines procedural CAD model generation, synthetic scene generation in Blender, automatic YOLO annotation, and deep learning-based object detection. The generated datasets are designed to support the development of vision-based fastener recognition systems, with a focus on applications in automated assembly and industrial environments.

## Project Overview

The repository is organized into four main processing stages:

| Stage | Directory | Description |
|---|---|---|
| 01 | `01_fastener_generation/` | Generation of labeled fastener CAD models |
| 02 | `02_distractor_generation/` | Generation of unlabeled objects used as distractors |
| 03 | `03_image_generation/` | Generation of synthetic images and YOLO annotations |
| 04 | `04_yolo_training/` | Dataset preparation, YOLO model training, and evaluation |

Each stage generates data that is used by the subsequent stage.

```text
CAD Model Generation
        |
        v
+-----------------------------+
| 01_fastener_generation      |
|                             |
| Screws, nuts, and fasteners |
| Labeled CAD models          |
+-----------------------------+
        |
        v
+-----------------------------+
| 02_distractor_generation    |
|                             |
| Additional CAD objects      |
| Unlabeled distractors       |
+-----------------------------+
        |
        v
+-----------------------------+
| 03_image_generation         |
|                             |
| Blender-based scene setup   |
| Synthetic image rendering   |
| Automatic YOLO annotations  |
+-----------------------------+
        |
        v
+-----------------------------+
| 04_yolo_training            |
|                             |
| Dataset preparation         |
| YOLO model training         |
| Model evaluation            |
+-----------------------------+
        |
        v
Trained YOLO Model
```

---

## 01 – Fastener Generation

**Directory:** `01_fastener_generation/`

This stage generates the CAD models of the fasteners that will be recognized by the YOLO model.

The objective is to create a diverse dataset of standardized fasteners, including different screw and nut geometries.

### Main functionalities

- Procedural generation of standard fastener geometries.
- Generation of different screw types and head geometries.
- Generation of nuts and other standardized fasteners.
- Export of individual CAD models as STL files.
- Automatic assignment of class information through metadata.

The generated fasteners are the target objects of the subsequent image generation and object detection pipeline.

### Output

The main output consists of:

- Individual STL files of the generated fasteners.
- `generated_metadata.csv`, containing the corresponding model information and class attributes.

The metadata file links each STL file to its corresponding class information. This information is used during synthetic image generation to assign YOLO class IDs.

---

## 02 – Distractor Generation

**Directory:** `02_distractor_generation/`

This stage generates additional CAD objects that are included in the synthetic scenes but are not part of the target classes.

These objects simulate the variety of components and visual clutter that can occur in real industrial assembly environments.

### Main functionalities

- Procedural generation of additional CAD geometries.
- Creation of different mechanical and industrial components.
- Export of individual objects as STL files.
- Generation of unlabeled objects for synthetic scene composition.

Distractors are deliberately not assigned YOLO class labels. They are included in the images to make the object detection task more challenging and to reduce the risk of models learning to recognize fasteners only in isolated scenes.

### Output

- Individual STL files of distractor objects.

These models are used by the image generation stage as unlabeled scene objects.

---

## 03 – Image Generation

**Directory:** `03_image_generation/`

This stage generates synthetic training images using Blender.

The generated fastener and distractor STL models are imported into Blender and automatically arranged to create multi-object scenes.

### Scene Generation

Each scene contains a randomized combination of target objects and distractors.

The generation process includes:

- Random selection of fastener models.
- Random selection of distractor models.
- Randomized object positions and orientations.
- Randomized object scaling.
- Assignment of different materials to target objects and distractors.
- Randomized camera positions and viewing angles.
- Randomized lighting conditions.
- Optional background photographs.

Target fasteners are assigned metallic materials representing different steel surface finishes. Distractors use a broader range of materials and colors.

### Automatic YOLO Annotation

YOLO bounding boxes are calculated automatically using the Blender camera projection.

For each target object, the eight corners of its world-space bounding box are projected into camera coordinates. The resulting image-space bounding box is converted into the normalized YOLO annotation format.

Distractors are rendered but remain unlabeled.

Negative scenes can also be generated. These images contain distractors but no target fasteners and therefore have empty annotation files.

### Image Resolution

The default target resolution is:

- Width: 1280 pixels
- Height: 720 pixels

This corresponds to the RGB image resolution of the Intel RealSense D405 camera used as a reference for the intended application.

The render resolution can be configured through environment variables.

### Configuration

Important parameters can be configured in the Docker Compose file:

| Parameter | Description |
|---|---|
| `SCENE_COUNT` | Number of scenes to generate |
| `TARGET_MIN` | Minimum number of target fasteners per scene |
| `TARGET_MAX` | Maximum number of target fasteners per scene |
| `DISTRACTOR_MIN` | Minimum number of distractors per scene |
| `DISTRACTOR_MAX` | Maximum number of distractors per scene |
| `NEGATIVE_SCENE_PROBABILITY` | Probability of generating a scene without target objects |
| `TABLE_SIZE` | Size of the virtual workspace |
| `RES_X` | Render width |
| `RES_Y` | Render height |
| `EEVEE_SAMPLES` | Number of Eevee render samples |
| `RANDOM_SEED` | Random seed for reproducibility |
| `CLASS_ATTRIBUTE` | Metadata attribute used for YOLO class assignment |

### Output Structure

Each generation run creates a new timestamped dataset directory:

```text
03_image_generation/
└── output/
    └── multi_object_dataset_YYYYMMDD_HHMMSS/
        ├── images/
        │   ├── scene_000000.png
        │   ├── scene_000001.png
        │   └── ...
        ├── labels/
        │   ├── scene_000000.txt
        │   ├── scene_000001.txt
        │   └── ...
        ├── classes.txt
        ├── class_mapping.json
        ├── metadata.csv
        └── input_errors.csv
```

The `images/` directory contains the rendered images.

The `labels/` directory contains the corresponding YOLO annotation files. Each line represents one target object:

```text
class_id x_center y_center width height
```

All coordinates and dimensions are normalized to the image width and height.

`class_mapping.json` stores the mapping between class names and numerical YOLO class IDs.

`metadata.csv` contains information about each generated scene, including the number of target objects, distractors, labels, and the background used.

---

## 04 – YOLO Training

**Directory:** `04_yolo_training/`

This stage prepares the synthetic dataset and trains YOLO object detection models using the generated images and annotations.

The training process is separated into dataset preparation and model training.

### Dataset Preparation

Before training, the generated dataset is processed and validated.

Main functionalities include:

- Identification of the latest generated image dataset.
- Validation of image and annotation files.
- Verification of image dimensions.
- Validation of YOLO bounding box annotations.
- Identification of images without labeled target objects.
- Splitting of complete scenes into training, validation, and test datasets.
- Generation of the YOLO dataset configuration file.
- Reuse of previously prepared datasets when the source data and configuration have not changed.

The dataset is split by complete scene, ensuring that all objects from a rendered scene remain in the same subset.

The default split ratios are:

- Training: 80%
- Validation: 10%
- Test: 10%

### YOLO Training

The training script loads the prepared dataset and trains a YOLO model.

Important configurable parameters include:

- Model architecture and pretrained weights.
- Image size.
- Batch size.
- Number of epochs.
- Learning rate.
- Early stopping patience.
- Number of data loading workers.
- Computing device (CPU or GPU).
- Random seed.

The training configuration can be adapted to the target hardware and available resources.

### Evaluation

After training, the best model weights are saved.

If a separate test split is available, the trained model is evaluated using the test dataset.

The evaluation provides information about the model's object detection performance on previously unseen synthetic scenes.

### Output

Typical training outputs include:

```text
04_yolo_training/
└── output/
    ├── datasets/
    │   └── screw_scene_dataset_*/
    │       ├── images/
    │       │   ├── train/
    │       │   ├── val/
    │       │   └── test/
    │       ├── labels/
    │       │   ├── train/
    │       │   ├── val/
    │       │   └── test/
    │       ├── dataset.yaml
    │       └── dataset_report.json
    │
    ├── weights/
    │   └── best.pt
    │
    └── runs/
```

The trained `best.pt` file contains the best-performing model weights and can be used for subsequent inference and evaluation.

---

## Installation and Requirements

The pipeline uses Docker to provide reproducible execution environments for the different processing stages.

### Requirements

- Windows, Linux, or another Docker-compatible operating system.
- Docker Desktop or Docker Engine.
- Docker Compose.
- Sufficient disk space for CAD models, rendered images, and training datasets.
- GPU support is recommended for faster YOLO training.

The individual processing stages use the dependencies defined in their respective Dockerfiles.

### Repository Setup

Clone the repository:

```bash
git clone https://github.com/JustusRein/YOLO-Screw-clustering.git
cd YOLO-Screw-clustering
```

Build the Docker images for the respective processing stages using their Docker Compose configurations.

---

## Running the Pipeline

The stages should be executed in the following order.

### Step 1 – Generate Fasteners

Navigate to:

```bash
cd 01_fastener_generation
```

Build and run the fastener generation service using its Docker Compose configuration.

The generated STL files and metadata are stored in:

```text
01_fastener_generation/output/
```

### Step 2 – Generate Distractors

Navigate to:

```bash
cd 02_distractor_generation
```

Build and run the distractor generation service.

The generated STL files are stored in:

```text
02_distractor_generation/output/stl/
```

### Step 3 – Generate Synthetic Images

Navigate to:

```bash
cd 03_image_generation
```

Build and run the image generation service:

```bash
docker compose build
docker compose run --rm image-generator
```

The generated images and YOLO annotations are stored in a new timestamped directory under:

```text
03_image_generation/output/
```

### Step 4 – Train the YOLO Model

Navigate to:

```bash
cd 04_yolo_training
```

Build and run the training service:

```bash
docker compose build
docker compose run --rm yolo-trainer
```

The training stage automatically prepares the dataset and starts model training.

The trained model weights and evaluation results are stored in the configured output directory.

---

## Reproducibility and Configuration

The pipeline uses configurable random seeds to support reproducible data generation and training.

The following aspects can be controlled independently:

- CAD model generation parameters.
- Fastener and distractor model selection.
- Scene composition and object placement.
- Camera position and orientation.
- Material and lighting configuration.
- Image resolution and rendering settings.
- Dataset splitting.
- YOLO training hyperparameters.

For reproducible experiments, the configuration files, random seeds, generated metadata, and dataset reports should be retained together with the corresponding model weights.

---

## Intended Application

The overall objective is to develop a vision-based fastener recognition system for industrial assembly environments.

The synthetic dataset provides a controlled way to generate images of different fastener types under varying conditions, including changes in object orientation, position, lighting, material appearance, and scene composition.

The resulting YOLO models can serve as a basis for recognizing and localizing screws, nuts, and other fasteners in camera images.

The synthetic data generation pipeline also provides a foundation for future extensions, such as:

- Additional standardized fastener types.
- More diverse mechanical components and distractors.
- Domain randomization and more realistic industrial backgrounds.
- Adaptation to real camera images.
- Evaluation using images acquired with an Intel RealSense D405.
- Integration into automated assembly and screw identification systems.

---

## License

Please refer to the repository license for information about usage, modification, and redistribution.

## Author

**Justus Rein**

GitHub: [JustusRein](https://github.com/JustusRein)

Repository: [YOLO-Screw-clustering](https://github.com/JustusRein/YOLO-Screw-clustering)