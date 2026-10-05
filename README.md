# 🛰️ Landsat Stacker

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Format](https://img.shields.io/badge/format-ERDAS%20Imagine%20(.img)-orange.svg)](https://www.hexagon.com/)
[![GIS Support](https://img.shields.io/badge/GIS-QGIS%20%7C%20ArcGIS%20Pro%20%7C%20ERDAS-blueviolet.svg)](#software-compatibility)

A robust, automated Python tool to validate and stack Landsat optical bands (**B1 through B7**) into a georeferenced 7-band **ERDAS Imagine (`.img`)** raster. Includes direct archive extraction (`.rar`, `.tar`, `.tar.gz`, `.zip`) and automatic generation of 4 calibrated full-color remote sensing PNG preview composites.

---

## ✨ Features

- 📦 **Direct Archive Drag & Drop**: Drop your raw downloaded `.rar`, `.tar`, `.tar.gz`, `.tgz`, or `.zip` archives directly into `input/`. The script automatically detects, unpacks (via local WinRAR/UnRAR or built-in tools), and filters out unwanted non-optical files (like QA masks).
- ⚙️ **Isolated Staging (`processing/`)**: Extracts and isolates only the required bands (`B1` to `B7`) in a dedicated staging directory, keeping your workspace tidy and reproducible.
- 🔍 **Strict Raster Validation**: Validates dimensions, spatial resolution, Coordinate Reference System (CRS), and geotransforms across all 7 bands before stacking begins.
- 🗺️ **Full 16-Bit Radiometric Fidelity**: Preserves full 16-bit sensor data into an ERDAS Imagine HFA multi-layer raster (`.img`) with overview pyramids (`[2, 4, 8, 16]`) for instantaneous panning and zooming in GIS software.
- 🎨 **Physical Surface Reflectance (SR) Preview Rendering**: Generates 4 vibrant, calibrated PNG composites with cloud-immune display stretching that matches the visual fidelity of ERDAS Imagine 2025.

---

## 📁 Project Structure

```text
landsat-stacker/
│
├── Landsat_Stacker.py             # Main stacking & extraction pipeline
├── compare_stacks.py              # Validation & visual comparison utility
├── README.md                      # Project documentation
├── Landsat_Stacker_Guide.docx     # Beginner & teaching guide
│
├── input/                         # Place your .rar, .tar, .zip, or raw .TIF files here
│   └── .gitkeep
│
├── processing/                    # Automated staging folder for B1–B7 files
│   └── .gitkeep
│
└── output/                        # Generated GIS raster & color preview composites
    ├── Landsat_Stacked.img        # 7-band 16-bit ERDAS Imagine raster stack
    ├── Landsat_TrueColor_Preview.png
    ├── Landsat_FalseColor_NIR_Preview.png
    ├── Landsat_Agriculture_Preview.png
    └── Landsat_Urban_Preview.png
```

---

## ⚙️ Prerequisites & Installation

### Requirements
- **Python 3.11+**
- **Rasterio** or **GDAL**
- **Pillow** & **NumPy**

### Quick Install (Windows / macOS / Linux)

Open your terminal or PowerShell and install the required dependencies:

```cmd
pip install rasterio numpy pillow
```

> **Note on WinRAR / UnRAR**:
> If you are dropping `.rar` files into `input/`, the script automatically detects your installed WinRAR / UnRAR (`C:\Program Files\WinRAR\UnRAR.exe`). For `.tar`, `.tar.gz`, and `.zip` archives, Python's built-in libraries handle extraction natively with zero configuration needed.

---

## 🚀 How to Use

### 1. Place Input Data
Cut and paste your downloaded Landsat dataset directly into the `input/` folder:
- **Compressed archives supported**: `.rar`, `.tar`, `.tar.gz`, `.tgz`, `.zip`, `.7z`
- **Loose files supported**: Uncompressed `*_B1.TIF` through `*_B7.TIF` files

### 2. Run the Script
```cmd
python Landsat_Stacker.py
```

### 3. Generated Output
The script automatically produces:
1. **`output/Landsat_Stacked.img`**: Full 16-bit 7-band ERDAS Imagine raster ready for analysis in ERDAS Imagine, ArcGIS Pro, or QGIS.
2. **`output/*.png`**: 4 full-resolution preview images viewable directly in Windows Photo Viewer or web browsers.

---

## 📊 Band Mapping

| Output Layer | Landsat Band | Wavelength | Spatial Resolution | Description |
| :---: | :---: | :---: | :---: | :--- |
| **Band 1** | **B1** | 0.43 – 0.45 µm | 30 m | Coastal Aerosol / Deep Blue |
| **Band 2** | **B2** | 0.45 – 0.51 µm | 30 m | Visible Blue |
| **Band 3** | **B3** | 0.53 – 0.59 µm | 30 m | Visible Green |
| **Band 4** | **B4** | 0.64 – 0.67 µm | 30 m | Visible Red |
| **Band 5** | **B5** | 0.85 – 0.88 µm | 30 m | Near Infrared (NIR) |
| **Band 6** | **B6** | 1.57 – 1.65 µm | 30 m | Shortwave Infrared 1 (SWIR 1) |
| **Band 7** | **B7** | 2.11 – 2.29 µm | 30 m | Shortwave Infrared 2 (SWIR 2) |

---

## 🎨 Automated Preview Composites

| Preview File | Band Combination | Remote Sensing Application |
| :--- | :---: | :--- |
| **`Landsat_TrueColor_Preview.png`** | **4 - 3 - 2** | **Natural True Color**: Natural human perception of Earth terrain |
| **`Landsat_FalseColor_NIR_Preview.png`** | **5 - 4 - 3** | **Standard FCC (NIR)**: Highlights vegetation health & density in bright red |
| **`Landsat_Agriculture_Preview.png`** | **6 - 5 - 2** | **Agriculture**: Highlights crop vigor, soil moisture, and bare fields |
| **`Landsat_Urban_Preview.png`** | **7 - 6 - 4** | **Urban / Geology**: Highlights concrete, roads, and rock formations |

---

## 🛠️ Software Compatibility

The output `.img` file is created using the native GDAL `HFA` driver, ensuring full native compatibility with:
- **ERDAS Imagine** (2025, 2022, 2020)
- **ArcGIS Pro / ArcMap**
- **QGIS** (3.x)

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
