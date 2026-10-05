import os
import sys
import re
import shutil
import zipfile
import tarfile
import subprocess
import numpy as np

# Dual support: Try rasterio first (pre-compiled binaries for Windows), fallback to osgeo.gdal
USE_RASTERIO = False
USE_GDAL = False

try:
    import rasterio
    from rasterio.enums import Resampling
    USE_RASTERIO = True
except ImportError:
    try:
        from osgeo import gdal, osr
        gdal.UseExceptions()
        USE_GDAL = True
    except ImportError:
        print("ERROR: Neither 'rasterio' nor 'GDAL' Python package is installed.")
        print("Please install rasterio using: pip install rasterio")
        sys.exit(1)


def extract_archive(archive_path, target_dir):
    """
    Extracts a compressed archive (.rar, .zip, .tar, .tar.gz, .tgz, .7z) into target_dir.
    Supports WinRAR / UnRAR on Windows, built-in tarfile/zipfile, and Windows tar.exe.
    """
    lower_name = archive_path.lower()
    os.makedirs(target_dir, exist_ok=True)

    # 1. ZIP Archives
    if lower_name.endswith(".zip"):
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(target_dir)
            return True
        except Exception as e:
            print(f"  [Notice] Python zipfile: {e}. Trying system tools...")

    # 2. TAR Archives (.tar, .tar.gz, .tgz, .tar.bz2)
    if lower_name.endswith((".tar.gz", ".tgz", ".tar", ".tar.bz2")):
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(target_dir)
            return True
        except Exception as e:
            print(f"  [Notice] Python tarfile: {e}. Trying system tools...")

    # 3. RAR Archives (.rar)
    if lower_name.endswith(".rar"):
        unrar_candidates = [
            r"C:\Program Files\WinRAR\UnRAR.exe",
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
            "unrar",
            "winrar"
        ]
        target_dir_slash = target_dir if target_dir.endswith(os.sep) else target_dir + os.sep

        for unrar_exe in unrar_candidates:
            if os.path.exists(unrar_exe) or shutil.which(unrar_exe):
                try:
                    cmd = [unrar_exe, "x", "-y", "-o+", archive_path, target_dir_slash]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res.returncode == 0:
                        return True
                except Exception:
                    pass

        try:
            import rarfile
            with rarfile.RarFile(archive_path, "r") as rf:
                rf.extractall(target_dir)
            return True
        except Exception:
            pass

    # 4. Fallback: Windows built-in tar.exe
    try:
        res = subprocess.run(["tar", "-xf", archive_path, "-C", target_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 5. Fallback: 7z if in PATH or standard Program Files
    seven_z = shutil.which("7z") or (r"C:\Program Files\7-Zip\7z.exe" if os.path.exists(r"C:\Program Files\7-Zip\7z.exe") else None)
    if seven_z:
        try:
            res = subprocess.run([seven_z, "x", "-y", f"-o{target_dir}", archive_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 6. Fallback: PowerShell Expand-Archive (for zip)
    if lower_name.endswith(".zip"):
        try:
            ps_cmd = f"Expand-Archive -LiteralPath '{archive_path}' -DestinationPath '{target_dir}' -Force"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


def prepare_processing_folder(input_dir, processing_dir):
    """
    Scans input_dir for Landsat data. If a compressed archive (.rar, .zip, .tar, etc.)
    is found, it automatically extracts it and copies ONLY the required B1 through B7 TIF files
    into the processing/ folder. If raw TIF files are already in input/, it copies them directly.
    """
    print("========================================")
    print("   PREPARING & EXTRACTING INPUT DATA   ")
    print("========================================\n")

    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)

    # Recreate clean processing directory
    if os.path.exists(processing_dir):
        try:
            shutil.rmtree(processing_dir, ignore_errors=True)
        except Exception:
            pass
    os.makedirs(processing_dir, exist_ok=True)

    archive_exts = (".rar", ".zip", ".tar.gz", ".tgz", ".tar", ".tar.bz2", ".7z")
    input_items = os.listdir(input_dir)
    archive_files = [f for f in input_items if f.lower().endswith(archive_exts)]

    temp_extract_dir = os.path.join(processing_dir, "_temp_extract")

    if archive_files:
        os.makedirs(temp_extract_dir, exist_ok=True)
        for archive_name in archive_files:
            archive_path = os.path.join(input_dir, archive_name)
            print(f"Detected archive: {archive_name}")
            print(f"Extracting '{archive_name}'...")
            success = extract_archive(archive_path, temp_extract_dir)
            if success:
                print(f"[OK] Extracted: {archive_name}\n")
            else:
                print(f"[WARNING] Could not extract '{archive_name}'. Checking if raw band files exist...\n")
    else:
        print("No compressed archive found in input/. Checking for raw band files...\n")

    # Pattern to identify Landsat B1 through B7 band files
    band_pattern = re.compile(r"(?:^|[\-_])B([1-7])\.(?:tif|tiff)$", re.IGNORECASE)

    search_dirs = []
    if os.path.exists(temp_extract_dir):
        search_dirs.append(temp_extract_dir)
    search_dirs.append(input_dir)

    found_bands = {}
    mtl_file = None

    for s_dir in search_dirs:
        for root, _, files in os.walk(s_dir):
            for fname in files:
                match = band_pattern.search(fname)
                if match:
                    b_num = int(match.group(1))
                    if b_num not in found_bands:
                        found_bands[b_num] = os.path.join(root, fname)
                if fname.upper().endswith("_MTL.TXT") and not mtl_file:
                    mtl_file = os.path.join(root, fname)

    missing_bands = [b for b in range(1, 8) if b not in found_bands]
    if missing_bands:
        print(f"ERROR: Missing Landsat band(s): {', '.join(f'B{b}' for b in missing_bands)} in input data.")
        print(f"Please place your Landsat .rar, .tar, .zip archive or B1-B7 .TIF files into:\n'{input_dir}'")
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        sys.exit(1)

    print("Copying required Landsat bands (B1–B7) into processing/ folder:")
    for b in range(1, 8):
        src_path = found_bands[b]
        dst_path = os.path.join(processing_dir, os.path.basename(src_path))
        shutil.copy2(src_path, dst_path)
        print(f"  [OK] B{b} -> {os.path.basename(dst_path)}")

    if mtl_file:
        shutil.copy2(mtl_file, os.path.join(processing_dir, os.path.basename(mtl_file)))
        print(f"  [OK] Metadata -> {os.path.basename(mtl_file)}")

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

    print("\n[OK] Processing folder prepared successfully.\n")


def find_bands(input_dir):
    """
    Scans input_dir for Landsat B1 through B7 TIF files.
    Returns a dictionary mapping band number (1..7) to file path.
    """
    if not os.path.exists(input_dir):
        print(f"ERROR: Folder '{input_dir}' does not exist.")
        sys.exit(1)

    band_files = {}

    band_pattern = re.compile(r"(?:^|[\-_])B([1-7])\.(?:tif|tiff)$", re.IGNORECASE)

    for filename in sorted(os.listdir(input_dir)):
        match = band_pattern.search(filename)
        if match:
            band_num = int(match.group(1))
            full_path = os.path.join(input_dir, filename)
            band_files[band_num] = full_path

    for b in range(1, 8):
        if b in band_files:
            print(f"[OK] B{b} found")
        else:
            print(f"\nERROR: B{b} was not found in processing folder.")
            sys.exit(1)

    return band_files


def validate_bands(band_files):
    """
    Validates that all 7 bands share identical width, height, CRS, pixel size, and geotransform.
    Returns metadata dict of reference band if validation passes.
    """
    print("\nValidating rasters...\n")

    if USE_RASTERIO:
        ref_file = band_files[1]
        with rasterio.open(ref_file) as ref_ds:
            ref_width = ref_ds.width
            ref_height = ref_ds.height
            ref_crs = ref_ds.crs
            ref_transform = ref_ds.transform
            ref_dtype = ref_ds.dtypes[0]
            ref_nodata = ref_ds.nodata if ref_ds.nodata is not None else 0

        for b in range(1, 8):
            with rasterio.open(band_files[b]) as ds:
                if ds.width != ref_width or ds.height != ref_height:
                    print(f"ERROR: Raster dimensions do not match. B1 is ({ref_width}x{ref_height}), B{b} is ({ds.width}x{ds.height}).")
                    sys.exit(1)
                if ds.crs != ref_crs:
                    print(f"ERROR: CRS mismatch for B{b}.")
                    sys.exit(1)
                if ds.transform != ref_transform:
                    print(f"ERROR: Geotransform / pixel size mismatch for B{b}.")
                    sys.exit(1)

        print("[OK] Dimensions")
        print("[OK] CRS")
        print("[OK] Pixel size")
        print("[OK] Geotransform")

        return {
            "width": ref_width,
            "height": ref_height,
            "crs": ref_crs,
            "transform": ref_transform,
            "datatype": ref_dtype,
            "nodata": ref_nodata,
        }

    else:
        ref_file = band_files[1]
        ref_ds = gdal.Open(ref_file, gdal.GA_ReadOnly)
        if not ref_ds:
            print(f"ERROR: Could not open {ref_file} with GDAL.")
            sys.exit(1)

        ref_width = ref_ds.RasterXSize
        ref_height = ref_ds.RasterYSize
        ref_gt = ref_ds.GetGeoTransform()
        ref_proj = ref_ds.GetProjection()
        ref_dtype = ref_ds.GetRasterBand(1).DataType
        ref_nodata = ref_ds.GetRasterBand(1).GetNoDataValue()
        if ref_nodata is None:
            ref_nodata = 0
        ref_ds = None

        for b in range(1, 8):
            filepath = band_files[b]
            ds = gdal.Open(filepath, gdal.GA_ReadOnly)
            if not ds:
                print(f"ERROR: Could not open {filepath} with GDAL.")
                sys.exit(1)

            width = ds.RasterXSize
            height = ds.RasterYSize
            gt = ds.GetGeoTransform()
            proj = ds.GetProjection()

            if width != ref_width or height != ref_height:
                print(f"ERROR: Raster dimensions do not match. B1 is ({ref_width}x{ref_height}), B{b} is ({width}x{height}).")
                sys.exit(1)

            if gt and ref_gt:
                for idx in range(6):
                    if abs(gt[idx] - ref_gt[idx]) > 1e-5:
                        print(f"ERROR: Geotransform / pixel size mismatch for B{b}.")
                        print(f"       Expected: {ref_gt}, Got: {gt}")
                        sys.exit(1)

            if proj != ref_proj:
                srs_ref = osr.SpatialReference(wkt=ref_proj)
                srs_curr = osr.SpatialReference(wkt=proj)
                if not srs_ref.IsSame(srs_curr):
                    print(f"ERROR: CRS mismatch for B{b}.")
                    sys.exit(1)

            ds = None

        print("[OK] Dimensions")
        print("[OK] CRS")
        print("[OK] Pixel size")
        print("[OK] Geotransform")

        return {
            "width": ref_width,
            "height": ref_height,
            "geotransform": ref_gt,
            "projection": ref_proj,
            "datatype": ref_dtype,
            "nodata": ref_nodata,
        }


def scale_band_to_8bit(data_array, nodata_val):
    """
    Scales 16-bit raw Landsat surface reflectance values to 8-bit (0-255).
    Kept for backward compatibility.
    """
    nodata_mask = data_array == nodata_val
    valid_pixels = data_array[~nodata_mask]

    if not np.any(valid_pixels):
        return np.zeros_like(data_array, dtype=np.uint8)

    p2, p98 = np.percentile(valid_pixels, [2, 98])

    if p98 == p2:
        scaled = np.zeros_like(data_array, dtype=np.float32)
    else:
        scaled = ((data_array.astype(np.float32) - p2) / (p98 - p2)) * 254.0 + 1.0

    scaled = np.clip(scaled, 1, 255)
    scaled[nodata_mask] = 0

    return scaled.astype(np.uint8)


def stretch_band_erdas_style(arr, max_refl=0.28):
    """
    Applies ERDAS Imagine-style natural surface reflectance stretch:
    Maps 0.0% to 28-52% ground reflectance with gamma mid-tone compensation.
    Eliminates cloud-induced darkening and matches ERDAS Imagine display fidelity.
    """
    mask = (arr == 0)
    # Check if Landsat Level-2 Surface Reflectance (DN offset ~7273)
    if np.median(arr[arr > 0]) > 5000:
        sr = arr * 0.0000275 - 0.2
        sr = np.clip(sr, 0.0, max_refl)
        norm = sr / max_refl
        norm = norm ** (1.0 / 1.35)
        out = (norm * 254.0 + 1.0)
    else:
        # Fallback for Top-of-Atmosphere / raw DN
        valid = arr[arr > 0]
        p2 = np.percentile(valid, 2)
        p_high = np.percentile(valid, 85)
        if p_high <= p2:
            p_high = p2 + 1.0
        norm = np.clip((arr.astype(np.float32) - p2) / (p_high - p2), 0.0, 1.0) ** (1.0 / 1.25)
        out = (norm * 254.0 + 1.0)

    out[mask] = 0
    return out.astype(np.uint8)


def create_all_previews(output_file, output_dir):
    """
    Generates 4 full-color ERDAS-quality PNG previews directly from the stacked raster:
      1. True Color (Bands 4-3-2)
      2. False Color NIR / FCC (Bands 5-4-3)
      3. Agriculture (Bands 6-5-2)
      4. Urban / Geology (Bands 7-6-4)
    """
    print("\nGenerating ERDAS-Quality Full-Color Preview Images...")

    composites = {
        "Landsat_TrueColor_Preview.png": (4, 3, 2, "True Color (Bands 4-3-2)"),
        "Landsat_FalseColor_NIR_Preview.png": (5, 4, 3, "Standard False Color / FCC (Bands 5-4-3)"),
        "Landsat_Agriculture_Preview.png": (6, 5, 2, "Agriculture (Bands 6-5-2)"),
        "Landsat_Urban_Preview.png": (7, 6, 4, "Urban / Geology (Bands 7-6-4)")
    }

    # Custom ground reflectance ceilings per wavelength for optimal color balance
    band_refl_limits = {
        2: 0.28,  # Blue
        3: 0.28,  # Green
        4: 0.28,  # Red
        5: 0.52,  # NIR (high vegetation reflectance)
        6: 0.45,  # SWIR-1
        7: 0.40   # SWIR-2
    }

    try:
        from PIL import Image
    except ImportError:
        Image = None

    if USE_RASTERIO:
        with rasterio.open(output_file) as ds:
            stretched_cache = {}
            for filename, (r_idx, g_idx, b_idx, desc) in composites.items():
                print(f"  Rendering {desc} -> {filename}...")
                for idx in (r_idx, g_idx, b_idx):
                    if idx not in stretched_cache:
                        stretched_cache[idx] = stretch_band_erdas_style(
                            ds.read(idx),
                            max_refl=band_refl_limits.get(idx, 0.30)
                        )

                r = stretched_cache[r_idx]
                g = stretched_cache[g_idx]
                b = stretched_cache[b_idx]
                out_path = os.path.join(output_dir, filename)

                if Image:
                    Image.fromarray(np.dstack([r, g, b])).save(out_path)
                else:
                    with rasterio.open(
                        out_path, "w", driver="PNG",
                        width=ds.width, height=ds.height, count=3, dtype="uint8"
                    ) as dst:
                        dst.write(r, 1)
                        dst.write(g, 2)
                        dst.write(b, 3)
                print(f"  [OK] Saved: {filename}")
    else:
        out_ds = gdal.Open(output_file, gdal.GA_ReadOnly)
        if out_ds:
            stretched_cache = {}
            for filename, (r_idx, g_idx, b_idx, desc) in composites.items():
                print(f"  Rendering {desc} -> {filename}...")
                for idx in (r_idx, g_idx, b_idx):
                    if idx not in stretched_cache:
                        stretched_cache[idx] = stretch_band_erdas_style(out_ds.GetRasterBand(idx).ReadAsArray())

                r = stretched_cache[r_idx]
                g = stretched_cache[g_idx]
                b = stretched_cache[b_idx]
                out_path = os.path.join(output_dir, filename)

                if Image:
                    Image.fromarray(np.dstack([r, g, b])).save(out_path)
                else:
                    png_driver = gdal.GetDriverByName("PNG")
                    if png_driver:
                        p_ds = png_driver.Create(out_path, out_ds.RasterXSize, out_ds.RasterYSize, 3, gdal.GDT_Byte)
                        p_ds.GetRasterBand(1).WriteArray(r)
                        p_ds.GetRasterBand(2).WriteArray(g)
                        p_ds.GetRasterBand(3).WriteArray(b)
                        p_ds = None
                print(f"  [OK] Saved: {filename}")
            out_ds = None


def create_stack(band_files, output_file, ref_info, scale_to_8bit=False):
    """
    Creates an ERDAS Imagine .img stacked raster from bands 1 to 7 using HFA driver.

    Note on Band Ordering & True Colour Composites:
    - Output band N directly corresponds to Landsat input Band N (Band 1 -> B1, Band 2 -> B2, ..., Band 7 -> B7).
    - For GIS display:
      * Landsat 8/9 True Colour Composite: RGB = Bands 4-3-2
      * Landsat 4/5/7 True Colour Composite: RGB = Bands 3-2-1
    """
    print(f"\nCreating stacked image ({'8-bit Color Display Stretched' if scale_to_8bit else '16-bit Raw Data'})...\n")

    out_dtype = "uint8" if scale_to_8bit else ref_info["datatype"]

    if USE_RASTERIO:
        profile = {
            "driver": "HFA",  # ERDAS Imagine format (.img)
            "count": 7,
            "width": ref_info["width"],
            "height": ref_info["height"],
            "dtype": out_dtype,
            "crs": ref_info["crs"],
            "transform": ref_info["transform"]
        }

        with rasterio.open(output_file, "w", **profile) as dst:
            for b in range(1, 8):
                with rasterio.open(band_files[b]) as src:
                    data = src.read(1)

                    if scale_to_8bit:
                        out_data = scale_band_to_8bit(data, ref_info["nodata"])
                    else:
                        out_data = data

                    dst.write(out_data, b)

                print(f"[OK] B{b} -> Output Band {b}")

            print("Building overviews...")
            dst.build_overviews([2, 4, 8, 16], Resampling.average)

    else:
        driver = gdal.GetDriverByName("HFA")
        if driver is None:
            print("ERROR: GDAL HFA driver (ERDAS Imagine) is not available.")
            sys.exit(1)

        gdal_dtype = gdal.GDT_Byte if scale_to_8bit else ref_info["datatype"]

        out_ds = driver.Create(
            output_file,
            ref_info["width"],
            ref_info["height"],
            7,
            gdal_dtype
        )

        if not out_ds:
            print(f"ERROR: Could not create ERDAS Imagine output file at '{output_file}'.")
            sys.exit(1)

        if ref_info["geotransform"]:
            out_ds.SetGeoTransform(ref_info["geotransform"])
        if ref_info["projection"]:
            out_ds.SetProjection(ref_info["projection"])

        for b in range(1, 8):
            in_ds = gdal.Open(band_files[b], gdal.GA_ReadOnly)
            in_band = in_ds.GetRasterBand(1)

            data = in_band.ReadAsArray()
            out_band = out_ds.GetRasterBand(b)

            if scale_to_8bit:
                out_data = scale_band_to_8bit(data, ref_info["nodata"])
            else:
                out_data = data

            out_band.WriteArray(out_data)
            out_band.FlushCache()
            in_ds = None

            print(f"[OK] B{b} -> Output Band {b}")

        print("\nBuilding overviews...")
        out_ds.BuildOverviews("AVERAGE", [2, 4, 8, 16])

        out_ds.FlushCache()
        out_ds = None


def verify_output(output_file, expected_info):
    """
    Verifies that output exists, matches expected band count, dimensions, CRS, and geotransform.
    """
    print("\nVerifying output...\n")

    if not os.path.exists(output_file):
        print(f"ERROR: Output file '{output_file}' was not created.")
        sys.exit(1)

    if USE_RASTERIO:
        with rasterio.open(output_file) as out_ds:
            if out_ds.count != 7:
                print(f"ERROR: Expected 7 bands in output, got {out_ds.count}.")
                sys.exit(1)
            print("[OK] 7 bands")

            if not out_ds.crs:
                print("ERROR: Missing CRS in output raster.")
                sys.exit(1)
            print("[OK] CRS")

            if out_ds.width != expected_info["width"] or out_ds.height != expected_info["height"]:
                print("ERROR: Output dimensions do not match expected specifications.")
                sys.exit(1)
            print("[OK] Dimensions")

            if not out_ds.transform:
                print("ERROR: Missing geotransform in output raster.")
                sys.exit(1)
            print("[OK] Geotransform")

    else:
        out_ds = gdal.Open(output_file, gdal.GA_ReadOnly)
        if not out_ds:
            print(f"ERROR: Could not open created output file '{output_file}'.")
            sys.exit(1)

        if out_ds.RasterCount != 7:
            print(f"ERROR: Expected 7 bands in output, got {out_ds.RasterCount}.")
            sys.exit(1)
        print("[OK] 7 bands")

        if not out_ds.GetProjection():
            print("ERROR: Missing CRS in output raster.")
            sys.exit(1)
        print("[OK] CRS")

        if out_ds.RasterXSize != expected_info["width"] or out_ds.RasterYSize != expected_info["height"]:
            print("ERROR: Output dimensions do not match expected specifications.")
            sys.exit(1)
        print("[OK] Dimensions")

        if not out_ds.GetGeoTransform():
            print("ERROR: Missing geotransform in output raster.")
            sys.exit(1)
        print("[OK] Geotransform")

        out_ds = None


def check_data_integrity(band_files, output_file):
    """
    Verifies output raster integrity.
    """
    print("\nChecking data integrity...\n")

    if USE_RASTERIO:
        with rasterio.open(output_file) as out_ds:
            for b in range(1, 8):
                data = out_ds.read(b)
                if np.max(data) == 0:
                    print(f"ERROR: Output Band {b} is empty!")
                    sys.exit(1)
                print(f"[OK] Band {b} data integrity verified")
    else:
        out_ds = gdal.Open(output_file, gdal.GA_ReadOnly)
        for b in range(1, 8):
            data = out_ds.GetRasterBand(b).ReadAsArray()
            if np.max(data) == 0:
                print(f"ERROR: Output Band {b} is empty!")
                sys.exit(1)
            print(f"[OK] Band {b} data integrity verified")
        out_ds = None


def main():
    print("========================================")
    print("         LANDSAT STACKER")
    print("========================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "input")
    processing_dir = os.path.join(base_dir, "processing")
    output_dir = os.path.join(base_dir, "output")
    output_file = os.path.join(output_dir, "Landsat_Stacked.img")

    # List of all 4 generated preview PNGs
    preview_files = [
        os.path.join(output_dir, "Landsat_TrueColor_Preview.png"),
        os.path.join(output_dir, "Landsat_FalseColor_NIR_Preview.png"),
        os.path.join(output_dir, "Landsat_Agriculture_Preview.png"),
        os.path.join(output_dir, "Landsat_Urban_Preview.png")
    ]

    # Create folders if missing
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)

    # Prompt user if output file already exists
    if os.path.exists(output_file):
        print(f"Existing output found.\n")
        if not sys.stdin.isatty() or "--force" in sys.argv or "-y" in sys.argv:
            response = "y"
        else:
            try:
                response = input("Overwrite? (y/n): ").strip().lower()
            except EOFError:
                response = "y"
        if response not in ["y", "yes"]:
            print("Operation cancelled by user.")
            sys.exit(0)

        try:
            base_path = os.path.splitext(output_file)[0]
            sidecar_exts = [".aux.xml", ".rrd", ".ige", ".ovr", ".aux"]
            files_to_remove = [output_file] + preview_files
            for ext in sidecar_exts:
                files_to_remove.append(output_file + ext)
                files_to_remove.append(base_path + ext)

            for f in set(files_to_remove):
                if os.path.exists(f):
                    os.remove(f)
        except PermissionError:
            print(f"ERROR: Could not overwrite '{os.path.basename(output_file)}' because it is open in a GIS application (ERDAS Imagine, ArcGIS Pro, or QGIS).")
            print("Please close the file in your GIS software and re-run.")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Could not delete existing output file or sidecars: {e}")
            sys.exit(1)

    # Step 1: Extract any archives (.rar, .zip, .tar, etc.) from input/ and copy B1-B7 into processing/
    prepare_processing_folder(input_dir, processing_dir)

    # Step 2: Read validated band files from processing/
    print("Searching processing folder...\n")
    band_files = find_bands(processing_dir)

    # Step 3: Validate, stack, verify (original sensitive algorithm untouched)
    ref_info = validate_bands(band_files)

    create_stack(band_files, output_file, ref_info, scale_to_8bit=False)

    verify_output(output_file, ref_info)

    check_data_integrity(band_files, output_file)

    # Step 4: Generate all 4 ERDAS-quality full-color preview composites
    create_all_previews(output_file, output_dir)

    print("\n========================================")
    print("SUCCESS")
    print("========================================")
    print(f"\nCreated:")
    print(f"  - Raster Stack  : output/Landsat_Stacked.img")
    print(f"  - True Color    : output/Landsat_TrueColor_Preview.png (Bands 4-3-2)")
    print(f"  - False Color   : output/Landsat_FalseColor_NIR_Preview.png (Bands 5-4-3)")
    print(f"  - Agriculture   : output/Landsat_Agriculture_Preview.png (Bands 6-5-2)")
    print(f"  - Urban / SWIR  : output/Landsat_Urban_Preview.png (Bands 7-6-4)\n")


if __name__ == "__main__":
    main()

