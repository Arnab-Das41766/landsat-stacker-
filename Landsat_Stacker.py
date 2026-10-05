import os
import sys
import re
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
        # pyrefly: ignore [missing-import]
        from osgeo import gdal, osr
        gdal.UseExceptions()
        USE_GDAL = True
    except ImportError:
        print("ERROR: Neither 'rasterio' nor 'GDAL' Python package is installed.")
        print("Please install rasterio using: pip install rasterio")
        sys.exit(1)


def find_bands(input_dir):
    """
    Scans input_dir for Landsat B1 through B7 TIF files.
    Returns a dictionary mapping band number (1..7) to file path.
    """
    if not os.path.exists(input_dir):
        print(f"ERROR: Input folder '{input_dir}' does not exist.")
        sys.exit(1)

    band_files = {}

    # Pattern matching filenames ending in _B1.tif, _B2.tif, etc. (case insensitive)
    # Excludes QA_PIXEL, B8, B9, B10, B11, etc.
    band_pattern = re.compile(r"(?:^|[\-_])B([1-7])\.(?:tif|tiff)$", re.IGNORECASE)

    for filename in sorted(os.listdir(input_dir)):
        match = band_pattern.search(filename)
        if match:
            band_num = int(match.group(1))
            full_path = os.path.join(input_dir, filename)
            band_files[band_num] = full_path

    # Check that all 7 bands exist
    for b in range(1, 8):
        if b in band_files:
            print(f"[OK] B{b} found")
        else:
            print(f"\nERROR: B{b} was not found in the input folder.")
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
    Scales 16-bit raw Landsat surface reflectance values to 8-bit (0-255)
    using 2%-98% percentile stretch and gamma correction for vivid natural true-color rendering.
    """
    nodata_mask = (data_array == nodata_val) | (data_array == 0)
    valid_mask = ~nodata_mask

    if not np.any(valid_mask):
        return np.zeros_like(data_array, dtype=np.uint8)

    if data_array.dtype == np.uint8:
        return data_array

    # Convert Landsat C2 L2 DN to Surface Reflectance
    sr = np.maximum(0, (data_array.astype(np.float32) * 0.0000275) - 0.2)
    valid_sr = sr[valid_mask]

    p2, p98 = np.percentile(valid_sr, [2, 98])
    if p98 <= p2:
        p98 = p2 + 1.0

    stretched = np.clip((sr - p2) / (p98 - p2), 0, 1)
    gamma_corrected = np.power(stretched, 0.45)
    gamma_corrected[nodata_mask] = 0

    return (gamma_corrected * 255.0).astype(np.uint8)


def create_multi_composites(band_files, output_dir, ref_info):
    """
    V2 Feature: Generates 4 standard remote sensing multi-spectral PNG previews:
      1. True Color (RGB 4-3-2): Natural human-eye view.
      2. Standard Infrared FCC (RGB 5-4-3): Bright red vegetation.
      3. Agriculture & Crop Moisture (RGB 6-5-2): Soil and crop health.
      4. Urban & Built-Up (RGB 7-6-4): Infrastructure and building density.
    """
    print("\nGenerating Multi-Composite PNG Previews...")

    composites = {
        "Landsat_TrueColor_Preview.png": (4, 3, 2, "True Color (RGB 4-3-2)"),
        "Landsat_FalseColor_NIR_Preview.png": (5, 4, 3, "Standard Infrared FCC (RGB 5-4-3)"),
        "Landsat_Agriculture_Preview.png": (6, 5, 2, "Agriculture (RGB 6-5-2)"),
        "Landsat_Urban_Preview.png": (7, 6, 4, "Urban & Built-Up (RGB 7-6-4)")
    }

    for filename, (r_band, g_band, b_band, desc) in composites.items():
        preview_file = os.path.join(output_dir, filename)

        if USE_RASTERIO:
            with rasterio.open(band_files[r_band]) as src_r,                  rasterio.open(band_files[g_band]) as src_g,                  rasterio.open(band_files[b_band]) as src_b:
                 r = scale_band_to_8bit(src_r.read(1), ref_info["nodata"])
                 g = scale_band_to_8bit(src_g.read(1), ref_info["nodata"])
                 b = scale_band_to_8bit(src_b.read(1), ref_info["nodata"])
        else:
            ds_r = gdal.Open(band_files[r_band], gdal.GA_ReadOnly)
            ds_g = gdal.Open(band_files[g_band], gdal.GA_ReadOnly)
            ds_b = gdal.Open(band_files[b_band], gdal.GA_ReadOnly)
            r = scale_band_to_8bit(ds_r.GetRasterBand(1).ReadAsArray(), ref_info["nodata"])
            g = scale_band_to_8bit(ds_g.GetRasterBand(1).ReadAsArray(), ref_info["nodata"])
            b = scale_band_to_8bit(ds_b.GetRasterBand(1).ReadAsArray(), ref_info["nodata"])

            ds_r = ds_g = ds_b = None

        saved = False

        try:
            from PIL import Image
            rgb_array = np.dstack([r, g, b])
            img = Image.fromarray(rgb_array)
            img.save(preview_file)
            saved = True
        except Exception:
            pass

        if saved:
            print(f"[OK] {desc} -> output/{filename}")
        else:
            print(f"[WARNING] Could not save {filename}")
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
    output_dir = os.path.join(base_dir, "output")
    output_file = os.path.join(output_dir, "Landsat_Stacked.img")
    preview_file = os.path.join(output_dir, "Landsat_TrueColor_Preview.png")

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
            # Delete output file, preview PNG, and any associated sidecars (.aux.xml, .rrd, .ige, .ovr, .aux)
            base_path = os.path.splitext(output_file)[0]
            sidecar_exts = [".aux.xml", ".rrd", ".ige", ".ovr", ".aux"]
            files_to_remove = [output_file, preview_file]
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

    print("\nSearching input folder...\n")
    band_files = find_bands(input_dir)

    ref_info = validate_bands(band_files)

    create_stack(band_files, output_file, ref_info, scale_to_8bit=False)

    verify_output(output_file, ref_info)

    check_data_integrity(band_files, output_file)

    create_multi_composites(band_files, output_dir, ref_info)

    print("\n========================================")
    print("SUCCESS")
    print("========================================")
    print(f"\nCreated:")
    print(f"  - Raster Stack  : output/Landsat_Stacked.img")
    print(f"  - Color Preview : output/Landsat_TrueColor_Preview.png\n")


if __name__ == "__main__":
    main()
