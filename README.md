# Landsat Stacker

A lightweight, single-file Python tool to validate and stack Landsat optical bands (B1–B7) into a georeferenced 7-band **ERDAS Imagine (`.img`)** raster.

---

## 📁 Project Structure

```text
landsat-stacker-/
│
├── Landsat_Stacker.py
├── README.md
│
├── input/
│   ├── LC09_L2SP_139045_..._SR_B1.TIF
│   ├── LC09_L2SP_139045_..._SR_B2.TIF
│   ├── LC09_L2SP_139045_..._SR_B3.TIF
│   ├── LC09_L2SP_139045_..._SR_B4.TIF
│   ├── LC09_L2SP_139045_..._SR_B5.TIF
│   ├── LC09_L2SP_139045_..._SR_B6.TIF
│   └── LC09_L2SP_139045_..._SR_B7.TIF
│
└── output/
    └── Landsat_Stacked.img
```

---

## ⚙️ Prerequisites & Installation

- **Python 3.11+**
- **Rasterio** or **GDAL**

### Installation on Windows 11

Open **Command Prompt** or **PowerShell** and run:

```cmd
pip install rasterio numpy
```

> **Why `rasterio`?**
> Standard `pip install GDAL` on Windows requires C++ compiler headers. `rasterio` distributes pre-compiled Windows wheel binaries with GDAL built-in, installing error-free in seconds. The script supports both libraries seamlessly.

---

## 🚀 How to Use

1. **Prepare Input Data**:
   Place your uncompressed Landsat TIFF files (`*_B1.TIF` through `*_B7.TIF`) inside the `input/` folder.
   *(Original USGS filenames like `LC09_L2SP_139045_20260915_..._SR_B1.TIF` are automatically detected; renaming is not required).*

2. **Run the Script**:
   ```cmd
   python Landsat_Stacker.py
   ```

3. **Get Your Output**:
   The stacked 7-band raster will be generated at `output/Landsat_Stacked.img`.

---

## 🔍 Validation Rules

Before creating the stack, the script validates that:
- All 7 bands (B1 through B7) are present in `input/`.
- All rasters share identical **width & height**.
- All rasters share identical **Coordinate Reference Systems (CRS)**.
- All rasters share matching **pixel sizes & geotransforms**.

If any band is missing or mismatched, the script halts with a clear error message without modifying any raster data.

---

## 📊 Band Mapping

| Output Band | Landsat Input Band | Description |
| :---: | :---: | :--- |
| **Band 1** | B1 | Coastal Aerosol / Blue |
| **Band 2** | B2 | Blue |
| **Band 3** | B3 | Green |
| **Band 4** | B4 | Red |
| **Band 5** | B5 | Near Infrared (NIR) |
| **Band 6** | B6 | Shortwave Infrared 1 (SWIR 1) |
| **Band 7** | B7 | Shortwave Infrared 2 (SWIR 2) |

---

## 💻 Console Output Example

```text
========================================
         LANDSAT STACKER
========================================

Searching input folder...

[OK] B1 found
[OK] B2 found
[OK] B3 found
[OK] B4 found
[OK] B5 found
[OK] B6 found
[OK] B7 found

Validating rasters...

[OK] Dimensions
[OK] CRS
[OK] Pixel size
[OK] Geotransform

Creating stacked image...

[OK] B1 → Output Band 1
[OK] B2 → Output Band 2
[OK] B3 → Output Band 3
[OK] B4 → Output Band 4
[OK] B5 → Output Band 5
[OK] B6 → Output Band 6
[OK] B7 → Output Band 7

Verifying output...

[OK] 7 bands
[OK] CRS
[OK] Dimensions
[OK] Geotransform

========================================
SUCCESS
========================================

Created:
output/Landsat_Stacked.img
```

---

## 🛠️ Software Compatibility

The output `.img` file is created using the native GDAL `HFA` driver, ensuring full compatibility with:
- **ERDAS Imagine**
- **ArcGIS Pro / ArcMap**
- **QGIS**

---

## 📝 License & Scope
This V1 utility focuses strictly on validating and stacking Landsat optical bands B1–B7. No automatic resampling or QA masking is performed.
