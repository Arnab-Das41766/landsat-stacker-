import os
import sys
import re

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


def create_stack(band_files, output_file, ref_info):
    """
    Creates an ERDAS Imagine .img stacked raster from bands 1 to 7 using HFA driver with STATISTICS=YES.

    Note on Band Ordering & True Colour Composites:
    - Output band N directly corresponds to Landsat input Band N (Band 1 -> B1, Band 2 -> B2, ..., Band 7 -> B7).
    - For GIS display:
      * Landsat 8/9 True Colour Composite: RGB = Bands 4-3-2
      * Landsat 4/5/7 True Colour Composite: RGB = Bands 3-2-1
    """
    print("\nCreating stacked image...\n")

    if USE_RASTERIO:
        # Build profile from scratch to avoid carrying GeoTIFF-specific parameters (tiled, blocksize, compress)
        profile = {
            "driver": "HFA",  # ERDAS Imagine format (.img)
            "count": 7,
            "width": ref_info["width"],
            "height": ref_info["height"],
            "dtype": ref_info["datatype"],
            "crs": ref_info["crs"],
            "transform": ref_info["transform"],
            "nodata": ref_info["nodata"],
            "STATISTICS": "YES"  # Enable GDAL HFA driver statistics creation option
        }

        with rasterio.open(output_file, "w", **profile) as dst:
            for b in range(1, 8):
                with rasterio.open(band_files[b]) as src:
                    data = src.read(1)
                    dst.write(data, b)

                print(f"[OK] B{b} -> Output Band {b}")

            # Note: STATISTICS=YES requests GDAL HFA driver to construct statistic/histogram headers,
            # while dst.statistics(b, approx=False) explicitly calculates exact min/max/mean/stddev values.
            print("\nComputing band statistics...")
            for b in range(1, 8):
                dst.statistics(b, approx=False)

            # Build overviews (pyramids) [2, 4, 8, 16]
            print("Building overviews...")
            dst.build_overviews([2, 4, 8, 16], Resampling.average)

    else:
        driver = gdal.GetDriverByName("HFA")
        if driver is None:
            print("ERROR: GDAL HFA driver (ERDAS Imagine) is not available.")
            sys.exit(1)

        # Pass STATISTICS=YES creation option to GDAL driver
        out_ds = driver.Create(
            output_file,
            ref_info["width"],
            ref_info["height"],
            7,
            ref_info["datatype"],
            options=["STATISTICS=YES"]
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

            if ref_info["nodata"] is not None:
                out_band.SetNoDataValue(ref_info["nodata"])

            out_band.WriteArray(data)
            out_band.FlushCache()

            # Note: ComputeStatistics(False) explicitly computes and records exact stats per band
            out_band.ComputeStatistics(False)

            in_ds = None

            print(f"[OK] B{b} -> Output Band {b}")

        # Build overviews (pyramids) [2, 4, 8, 16]
        print("\nBuilding overviews...")
        out_ds.BuildOverviews("AVERAGE", [2, 4, 8, 16])

        out_ds.FlushCache()
        out_ds = None


def verify_output(output_file, expected_info):
    """
    Verifies that output exists, matches expected band count, dimensions, CRS, geotransform,
    datatype, nodata, and has stored band statistics.
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

            if out_ds.dtypes[0] != expected_info["datatype"]:
                print(f"ERROR: Datatype mismatch. Expected {expected_info['datatype']}, got {out_ds.dtypes[0]}.")
                sys.exit(1)
            print("[OK] Datatype")

            if out_ds.nodata is None:
                print("ERROR: NoData value is not set on output raster.")
                sys.exit(1)
            print("[OK] NoData value")

            for b in range(1, 8):
                tags = out_ds.tags(b)
                if not ("STATISTICS_MINIMUM" in tags or "STATISTICS_MAXIMUM" in tags):
                    print(f"ERROR: Band {b} lacks stored statistics tags!")
                    sys.exit(1)

            print("[OK] Stored Statistics")

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

        if out_ds.GetRasterBand(1).DataType != expected_info["datatype"]:
            print("ERROR: Datatype mismatch in output raster.")
            sys.exit(1)
        print("[OK] Datatype")

        for b in range(1, 8):
            band = out_ds.GetRasterBand(b)
            if band.GetNoDataValue() is None:
                print(f"ERROR: NoData value is not set on Band {b}!")
                sys.exit(1)
            meta = band.GetMetadata()
            if "STATISTICS_MINIMUM" not in meta:
                stats = band.GetStatistics(False, False)
                if stats is None:
                    print(f"ERROR: Band {b} lacks stored statistics!")
                    sys.exit(1)

        print("[OK] NoData value")
        print("[OK] Stored Statistics")

        out_ds = None


def check_data_integrity(band_files, output_file):
    """
    Reads each input band and the matching output band and confirms np.array_equal is True.
    """
    import numpy as np
    print("\nChecking data integrity...\n")

    if USE_RASTERIO:
        with rasterio.open(output_file) as out_ds:
            for b in range(1, 8):
                with rasterio.open(band_files[b]) as in_ds:
                    in_data = in_ds.read(1)
                    out_data = out_ds.read(b)
                    if not np.array_equal(in_data, out_data):
                        print(f"ERROR: Data mismatch between input B{b} and output Band {b}!")
                        sys.exit(1)
                    print(f"[OK] Band {b} pixel data matches input")
    else:
        out_ds = gdal.Open(output_file, gdal.GA_ReadOnly)
        for b in range(1, 8):
            in_ds = gdal.Open(band_files[b], gdal.GA_ReadOnly)
            in_data = in_ds.GetRasterBand(1).ReadAsArray()
            out_data = out_ds.GetRasterBand(b).ReadAsArray()
            in_ds = None
            if not np.array_equal(in_data, out_data):
                print(f"ERROR: Data mismatch between input B{b} and output Band {b}!")
                sys.exit(1)
            print(f"[OK] Band {b} pixel data matches input")
        out_ds = None


def main():
    print("========================================")
    print("         LANDSAT STACKER")
    print("========================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    output_file = os.path.join(output_dir, "Landsat_Stacked.img")

    # Create folders if missing
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)

    # Prompt user if output file already exists
    if os.path.exists(output_file):
        print(f"Existing output found.\n")
        try:
            response = input("Overwrite? (y/n): ").strip().lower()
        except EOFError:
            response = "y"
        if response not in ["y", "yes"]:
            print("Operation cancelled by user.")
            sys.exit(0)

        try:
            # Delete output file and any associated sidecars (.aux.xml, .rrd, .ige, .ovr, .aux)
            base_path = os.path.splitext(output_file)[0]
            sidecar_exts = [".aux.xml", ".rrd", ".ige", ".ovr", ".aux"]
            files_to_remove = [output_file]
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

    create_stack(band_files, output_file, ref_info)

    verify_output(output_file, ref_info)

    check_data_integrity(band_files, output_file)

    print("\n========================================")
    print("SUCCESS")
    print("========================================")
    print(f"\nCreated:\noutput/Landsat_Stacked.img\n")


if __name__ == "__main__":
    main()
