import sys
import os
import numpy as np

try:
    import rasterio
except ImportError:
    print("ERROR: 'rasterio' package is required for compare_stacks.py.")
    print("Please install it using: pip install rasterio matplotlib")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("ERROR: 'matplotlib' package is required to save RGB preview.")
    print("Please install it using: pip install matplotlib")
    sys.exit(1)


def compare(path1, path2):
    print("========================================")
    print("         STACK COMPARISON TOOL")
    print("========================================\n")

    if not os.path.exists(path1):
        print(f"ERROR: File 1 does not exist: {path1}")
        sys.exit(1)
    if not os.path.exists(path2):
        print(f"ERROR: File 2 does not exist: {path2}")
        sys.exit(1)

    print(f"File 1 (My Stack): {path1}")
    print(f"File 2 (Reference): {path2}\n")

    with rasterio.open(path1) as ds1, rasterio.open(path2) as ds2:
        print("--- Basic Metadata ---")
        print(f"File 1 -> dtype: {ds1.dtypes[0]}, nodata: {ds1.nodata}")
        print(f"File 2 -> dtype: {ds2.dtypes[0]}, nodata: {ds2.nodata}\n")

        print("--- Band Statistics & Array Comparison (Bands 2, 3, 4) ---")
        for b in [2, 3, 4]:
            arr1 = ds1.read(b)
            arr2 = ds2.read(b)

            equal = np.array_equal(arr1, arr2)

            nodata1 = ds1.nodata if ds1.nodata is not None else 0
            nodata2 = ds2.nodata if ds2.nodata is not None else 0

            mask1 = arr1 != nodata1
            mask2 = arr2 != nodata2

            p2_1, p98_1 = np.percentile(arr1[mask1], [2, 98]) if np.any(mask1) else (0, 0)
            p2_2, p98_2 = np.percentile(arr2[mask2], [2, 98]) if np.any(mask2) else (0, 0)

            print(f"Band {b}:")
            print(f"  Arrays Equal                           : {equal}")
            print(f"  File 1 Non-Zero Percentiles (2%, 98%) : ({p2_1:.2f}, {p98_1:.2f})")
            print(f"  File 2 Non-Zero Percentiles (2%, 98%) : ({p2_2:.2f}, {p98_2:.2f})\n")

        # Build RGB preview from Bands 4 (Red), 3 (Green), 2 (Blue) of File 1
        print("--- Generating RGB Composite Preview (Bands 4-3-2) ---")
        b4 = ds1.read(4).astype(np.float32)
        b3 = ds1.read(3).astype(np.float32)
        b2 = ds1.read(2).astype(np.float32)

        nodata1 = ds1.nodata if ds1.nodata is not None else 0
        valid_mask = (b4 != nodata1) & (b3 != nodata1) & (b2 != nodata1)

        def percentile_stretch(band, mask):
            if not np.any(mask):
                return np.zeros_like(band)
            pmin, pmax = np.percentile(band[mask], [2, 98])
            if pmax == pmin:
                return np.zeros_like(band)
            stretched = (band - pmin) / (pmax - pmin)
            return np.clip(stretched, 0, 1)

        r = percentile_stretch(b4, valid_mask)
        g = percentile_stretch(b3, valid_mask)
        b = percentile_stretch(b2, valid_mask)

        rgb = np.dstack([r, g, b])

        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(rgb)
        ax.set_title("True Colour Composite (Bands 4-3-2) Preview - 2% to 98% Stretch")
        ax.axis("off")

        output_png = "preview.png"
        plt.savefig(output_png, bbox_inches="tight", dpi=150)
        plt.close(fig)
        print(f"[OK] RGB preview saved as '{output_png}'.\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compare_stacks.py <path_to_my_stack.img> <path_to_ref_stack.img>")
        sys.exit(1)

    compare(sys.argv[1], sys.argv[2])
