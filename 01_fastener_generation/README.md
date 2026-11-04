# STEP-to-YOLO Screw Dataset Generator

Dieses Projekt durchsucht einen Eingabeordner rekursiv nach `.step`- und `.stp`-Dateien, importiert die Geometrie mit StepForge, rendert mehrere Ansichten und erzeugt **fünf voneinander unabhängige YOLO-Detection-Datensätze**.

Die fünf Datensätze verwenden dieselben Bilder und dieselbe Bounding Box. Pro Datensatz wird jedoch nur ein Attribut als Klassenlabel verwendet:

1. `screw_type`
2. `tool_size`
3. `thread_size`
4. `thread_pitch`
5. `screw_length`

Die Metadaten werden aus dem Dateinamen gelesen und können über `input/screw_metadata.csv` überschrieben werden. Es wird **nicht versucht, Gewinde, Steigung, Werkzeuggröße oder Schraubentyp aus der STEP-Geometrie zu erraten**.

---

## 1. Exaktes Dateinamen-Schema

Jede STEP-Datei muss nach diesem Schema benannt sein:

```text
DIN_<NUMMER>_M<GEWINDE>_P<STEIGUNG>_<WERKZEUGART><WERKZEUGGRÖSSE>_L<LÄNGE>.step
```

Beispiele:

```text
DIN_912_M5_P0.8_HEX4_L20.step
DIN_961_M6_P0.75_SW10_L30.step
DIN_7991_M5_P0.8_HEX3_L16.step
ISO_7380_M6_P1.0_HEX4_L20.step
DIN_934_M8_P1.25_SW13_LNA.step
```

`DIN` kann auch `ISO` oder `EN` sein. Die Werkzeuggröße kann mit oder ohne Unterstrich geschrieben werden, zum Beispiel `HEX4` oder `HEX_4`. Für eine einheitliche Ablage wird die Schreibweise ohne zusätzlichen Unterstrich empfohlen.

### Bedeutung der Dateinamen-Bestandteile

| Bestandteil | Bedeutung | Beispiel | Ergebnislabel |
|---|---|---|---|
| `DIN_912` | DIN-/ISO-Standard | `DIN_912` | Typ wird über die Standardtabelle zugeordnet |
| `M5` | Nenndurchmesser des Gewindes | `M5` | `M5` |
| `P0.8` | Gewindesteigung in mm | `P0.8` | `P0.8` |
| `HEX4` | Innensechskant, Schlüsselweite/Antrieb 4 mm | `HEX4` | `HEX4` |
| `SW10` | Außensechskant, Schlüsselweite 10 mm | `SW10` | `SW10` |
| `TX25` | Torx-Antrieb TX25 | `TX25` | `TX25` |
| `L20` | Schraubenlänge 20 mm | `L20` | `L20` |
| `LNA` | Keine Schraubenlänge vorhanden, z. B. Mutter | `LNA` | `NA` |

**Wichtig:** `tool_size` ist absichtlich eine gemeinsame Klasse aus Werkzeugfamilie und Größe. `HEX4`, `TX4` und `SW4` sind unterschiedliche Klassen. Nur die Zahl `4` wäre nicht eindeutig.

Dezimalwerte dürfen mit Punkt geschrieben werden. Der Parser akzeptiert auch Kommas und normalisiert sie intern auf einen Punkt. Empfohlen ist der Punkt.

---

## 2. Exakte Zuordnung des Schraubentyps (`screw_type`)

Der Schraubentyp wird nicht allein aus der Geometrie erkannt. Der Generator verwendet die explizite Tabelle `DIN_TO_SCREW_TYPE` in `scripts/metadata.py`.

Die folgenden Standards sind bereits eingetragen:

| Standard | `screw_type`-Label |
|---|---|
| `DIN_912` | `Socket_Head_Cap_Screw` |
| `DIN_931` | `Hex_Head_Screw` |
| `DIN_933` | `Hex_Head_Screw` |
| `DIN_961` | `Hex_Head_Screw` |
| `DIN_7984` | `Low_Head_Socket_Head_Screw` |
| `DIN_7991` | `Countersunk_Socket_Head_Screw` |
| `DIN_934` | `Hex_Nut` |
| `ISO_7380` | `Button_Head_Screw` |
| `ISO_4762` | `Socket_Head_Cap_Screw` |

Die Tabelle ist eine **editierbare Ausgangszuordnung**. Vor dem produktiven Einsatz muss geprüft werden, ob die jeweilige STEP-Datei tatsächlich die entsprechende Normausführung enthält. Bei Sonderformen, abweichenden Antrieben oder nicht hinterlegten Standards ist das Label in der CSV explizit anzugeben.

### Eigene Schraubentypen ergänzen

Öffne `scripts/metadata.py` und ergänze beispielsweise:

```python
DIN_TO_SCREW_TYPE = {
    "DIN_912": "Socket_Head_Cap_Screw",
    "DIN_7991": "Countersunk_Socket_Head_Screw",
    "ISO_7380": "Button_Head_Screw",
    "DIN_934": "Hex_Nut",

    # Eigene, zuvor geprüfte Zuordnungen:
    "DIN_XXXX": "Button_Head_Torx_Screw",
}
```

Der Wert rechts wird exakt als YOLO-Klassenname verwendet. Verwende für gleiche Typen immer exakt dieselbe Schreibweise.

---

## 3. CSV-Datei für manuelle Korrekturen

Die Datei `input/screw_metadata.csv` ist optional. Sie überschreibt die Werte aus dem Dateinamen. Das ist insbesondere dann sinnvoll, wenn:

- ein Standard noch nicht in `DIN_TO_SCREW_TYPE` enthalten ist,
- ein Standard mehrere Varianten abdecken kann,
- ein Sondertyp wie `Button_Head_Torx_Screw` explizit benannt werden soll,
- einzelne Dateien falsch oder unvollständig benannt sind.

Die Kopfzeile lautet:

```csv
relative_path,screw_type,tool_size,thread_size,thread_pitch,screw_length
```

Beispiel:

```csv
relative_path,screw_type,tool_size,thread_size,thread_pitch,screw_length
DIN_912/DIN_912_M5_P0.8_HEX4_L20.step,Socket_Head_Cap_Screw,HEX4,M5,P0.8,L20
Special/DIN_XXXX_M6_P1.0_TX25_L20.step,Button_Head_Torx_Screw,TX25,M6,P1.0,L20
DIN_934/DIN_934_M8_P1.25_SW13_LNA.step,Hex_Nut,SW13,M8,P1.25,NA
```

`relative_path` ist relativ zum `input`-Ordner und sollte verwendet werden, wenn verschiedene Unterordner gleichnamige Dateien enthalten. Alternativ kann die Spalte `filename` verwendet werden, sofern jeder Dateiname eindeutig ist.

Leere CSV-Felder überschreiben das jeweilige Dateinamenlabel nicht. Nicht erkannte oder fehlende Labels führen dazu, dass die Datei übersprungen und in `metadata.csv` mit einer Fehlermeldung dokumentiert wird. Es wird kein `Unknown`-Label erzeugt.

---

## 4. Beispiel für die Ordnerstruktur

Der Generator sucht rekursiv. Du kannst die STEP-Dateien nach Norm, Typ oder Lieferant sortieren:

```text
step_screw_yolo/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── scripts/
│   ├── metadata.py
│   └── generate_step_dataset.py
├── docker/
│   └── entrypoint.sh
├── input/
│   ├── screw_metadata.csv
│   ├── DIN_912/
│   │   ├── DIN_912_M5_P0.8_HEX4_L20.step
│   │   └── DIN_912_M6_P1.0_HEX5_L25.step
│   ├── DIN_7991/
│   │   └── DIN_7991_M5_P0.8_HEX3_L16.step
│   └── DIN_934/
│       └── DIN_934_M8_P1.25_SW13_LNA.step
└── output/
```

Eine STEP-Datei soll genau **eine physische Schraube oder Mutter** repräsentieren. Ein Modell darf aus mehreren CAD-Solids bestehen, beispielsweise Kopf und Schaft. Diese Solids werden als ein gemeinsames Objekt gerendert. Enthält eine STEP-Datei dagegen mehrere einzelne Schrauben, werden sie aktuell gemeinsam als ein Objekt gelabelt; solche Dateien müssen vorher getrennt werden.

---

## 5. Installation und Ausführung unter Windows

Voraussetzungen:

- Windows 10/11
- Docker Desktop installiert und gestartet
- Internetverbindung beim ersten Build

In PowerShell in den Projektordner wechseln:

```powershell
docker compose build
docker compose run --rm screw-dataset-generator
```

Die Eingabe wird aus `input/` gelesen. Das Ergebnis wird in einem neuen Zeitstempelordner unter `output/` abgelegt. Bestehende Datensätze werden nicht überschrieben.

Einstellungen wie Bildanzahl und Auflösung können in `docker-compose.yml` geändert werden:

```yaml
IMAGES_PER_STEP: "30"
RES_X: "640"
RES_Y: "640"
STEP_DEFLECTION: "0.025"
```

`STEP_DEFLECTION` steuert die Tessellierungsgenauigkeit. Kleinere Werte erzeugen feinere Netze, benötigen aber mehr Zeit und Speicher.

---

## 6. Ausgabe

Beispiel:

```text
output/
└── screw_dataset_YYYYMMDD_HHMMSS/
    ├── screw_type/
    │   ├── images/train|val|test/
    │   ├── labels/train|val|test/
    │   └── classes.txt
    ├── tool_size/
    │   ├── images/train|val|test/
    │   ├── labels/train|val|test/
    │   └── classes.txt
    ├── thread_size/
    │   ├── images/train|val|test/
    │   ├── labels/train|val|test/
    │   └── classes.txt
    ├── thread_pitch/
    │   ├── images/train|val|test/
    │   ├── labels/train|val|test/
    │   └── classes.txt
    ├── screw_length/
    │   ├── images/train|val|test/
    │   ├── labels/train|val|test/
    │   └── classes.txt
    ├── data_screw_type.yaml
    ├── data_tool_size.yaml
    ├── data_thread_size.yaml
    ├── data_thread_pitch.yaml
    ├── data_screw_length.yaml
    └── metadata.csv
```

Die fünf Datensätze enthalten dieselben gerenderten Ansichten. Für jedes Bild existiert je Attribut eine eigene Labeldatei. Die Klassen-IDs sind innerhalb des jeweiligen Attributs konsistent und werden alphabetisch erzeugt.

Die Aufteilung in Training, Validation und Test erfolgt **auf Ebene der STEP-Datei**. Alle Ansichten derselben Schraube landen damit im selben Split. Das verhindert, dass nahezu identische Ansichten einer Schraube gleichzeitig in Training und Test vorkommen.

`metadata.csv` dokumentiert Dateiname, relativen Pfad, Split, alle fünf Labels, Anzahl erzeugter Bilder und eventuelle Fehler.

---

## 7. YOLO-Training

Installiere Ultralytics in deiner Trainingsumgebung:

```powershell
pip install ultralytics
```

Trainiere anschließend fünf separate Modelle. Beispiel:

```powershell
yolo detect train model=yolo11n.pt data="output/screw_dataset_YYYYMMDD_HHMMSS/data_screw_type.yaml" epochs=100 imgsz=640
yolo detect train model=yolo11n.pt data="output/screw_dataset_YYYYMMDD_HHMMSS/data_tool_size.yaml" epochs=100 imgsz=640
yolo detect train model=yolo11n.pt data="output/screw_dataset_YYYYMMDD_HHMMSS/data_thread_size.yaml" epochs=100 imgsz=640
yolo detect train model=yolo11n.pt data="output/screw_dataset_YYYYMMDD_HHMMSS/data_thread_pitch.yaml" epochs=100 imgsz=640
yolo detect train model=yolo11n.pt data="output/screw_dataset_YYYYMMDD_HHMMSS/data_screw_length.yaml" epochs=100 imgsz=640
```

Das sind fünf unabhängige Modelle, nicht ein einzelnes Multi-Head-Modell. Jedes Modell lokalisiert die Schraube und sagt genau ein Attribut voraus.

---

## 8. Technische Hinweise und Grenzen

- Blender besitzt keinen nativen STEP-Importer. Dieses Projekt verwendet StepForge zur STEP-Auswertung und Tessellierung.
- StepForge berücksichtigt die in STEP gespeicherten Assembly-Instanztransformationen, bevor die Solids als Blender-Meshes angelegt werden.
- Die STEP-Geometrie liefert die Bildgeometrie und Bounding Box. Die semantischen Labels stammen aus Dateiname und CSV.
- Der Generator erzeugt synthetische Renderings, keine realen Kamerabilder. Für den späteren Einsatz ist eine Prüfung mit realen Aufnahmen erforderlich.
- Die Bounding Box umfasst alle Solids einer STEP-Datei gemeinsam.
- Bei Muttern wird `screw_length=NA` verwendet. Damit lernt das Längenmodell eine explizite Klasse `NA`; wenn du Muttern nicht im Längenmodell berücksichtigen möchtest, müssen sie aus diesem Attribut-Datensatz ausgeschlossen werden.
- Bei sehr wenigen STEP-Dateien können Validation oder Test leer bleiben. Für aussagekräftige Evaluation werden mehrere unterschiedliche CAD-Modelle pro Klasse benötigt.
- Die Standardzuordnung ist keine automatische Normenprüfung. Vor dem Training müssen die Dateinamen, die CSV und die resultierenden Klassen in `metadata.csv` kontrolliert werden.
