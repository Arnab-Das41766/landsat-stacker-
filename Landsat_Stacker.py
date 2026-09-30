import os
import sys
import re

# Dual support: Try rasterio first (pre-compiled binaries for Windows), fallback to osgeo.gdal
USE_RASTERIO = False
USE_GDAL = False

try:
    import rasterio
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
            ref_nodata = ref_ds.nodata

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
        }


def create_stack(band_files, output_file, ref_info):
    """
    Creates an ERDAS Imagine .img stacked raster from bands 1 to 7 using HFA driver.
    """
    print("\nCreating stacked image...\n")

    if USE_RASTERIO:
        with rasterio.open(band_files[1]) as ref_ds:
            profile = ref_ds.profile.copy()
            profile.update(
                driver="HFA",  # ERDAS Imagine format (.img)
                count=7,
                width=ref_info["width"],
                height=ref_info["height"],
                dtype=ref_info["datatype"],
                crs=ref_info["crs"],
                transform=ref_info["transform"],
                nodata=ref_info["nodata"]
            )

        with rasterio.open(output_file, "w", **profile) as dst:
            for b in range(1, 8):
                with rasterio.open(band_files[b]) as src:
                    data = src.read(1)
                    dst.write(data, b)

                print(f"[OK] B{b} \u2192 Output Band {b}")

    else:
        driver = gdal.GetDriverByName("HFA")
        if driver is None:
            print("ERROR: GDAL HFA driver (ERDAS Imagine) is not available.")
            sys.exit(1)

        out_ds = driver.Create(
            output_file,
            ref_info["width"],
            ref_info["height"],
            7,
            ref_info["datatype"]
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
            out_band.WriteArray(data)

            nodata = in_band.GetNoDataValue()
            if nodata is not None:
                out_band.SetNoDataValue(nodata)

            out_band.FlushCache()
            in_ds = None

            print(f"[OK] B{b} \u2192 Output Band {b}")

        out_ds.FlushCache()
        out_ds = None


def verify_output(output_file, expected_info):
    """
    Verifies that the output file exists and matches expected band count, dimensions, CRS, and geotransform.
    """
    print("\nVerifying output...\n")

    if not os.path.exists(output_file):
        print(f"ERROR: Output file '{output_file}' was not created.")
        sys.exit(1)

    if USE_RASTERIO:
        with rasterio.open(output_file) as out_ds:
            if out_ds.count == 7:
                print("[OK] 7 bands")
            else:
                print(f"ERROR: Expected 7 bands in output, got {out_ds.count}.")
                sys.exit(1)

            if out_ds.crs:
                print("[OK] CRS")

            if out_ds.width == expected_info["width"] and out_ds.height == expected_info["height"]:
                print("[OK] Dimensions")
            else:
                print("ERROR: Output dimensions do not match expected specifications.")
                sys.exit(1)

            if out_ds.transform:
                print("[OK] Geotransform")

    else:
        out_ds = gdal.Open(output_file, gdal.GA_ReadOnly)
        if not out_ds:
            print(f"ERROR: Could not open created output file '{output_file}'.")
            sys.exit(1)

        if out_ds.RasterCount == 7:
            print("[OK] 7 bands")
        else:
            print(f"ERROR: Expected 7 bands in output, got {out_ds.RasterCount}.")
            sys.exit(1)

        if out_ds.GetProjection():
            print("[OK] CRS")

        if out_ds.RasterXSize == expected_info["width"] and out_ds.RasterYSize == expected_info["height"]:
            print("[OK] Dimensions")
        else:
            print("ERROR: Output dimensions do not match expected specifications.")
            sys.exit(1)

        if out_ds.GetGeoTransform():
            print("[OK] Geotransform")

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
            os.remove(output_file)
            aux_file = output_file + ".aux.xml"
            if os.path.exists(aux_file):
                os.remove(aux_file)
        except Exception as e:
            print(f"ERROR: Could not delete existing output file: {e}")
            sys.exit(1)

    print("\nSearching input folder...\n")
    band_files = find_bands(input_dir)

    ref_info = validate_bands(band_files)

    create_stack(band_files, output_file, ref_info)

    verify_output(output_file, ref_info)

    print("\n========================================")
    print("SUCCESS")
    print("========================================")
    print(f"\nCreated:\noutput/Landsat_Stacked.img\n")


if __name__ == "__main__":
    main()
