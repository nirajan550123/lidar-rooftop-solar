"""
Optional QC step (Austin): export slope and aspect rasters from the DSM so you
can eyeball them in QGIS/ArcGIS before running the per-building aggregation.
Not required for the pipeline, but good for the writeup figures.

Usage:
    python src/terrain_metrics.py --dsm outputs/austin/dsm.tif --out-dir outputs/austin
"""

import argparse
import os
import sys

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(__file__))
from solar_suitability import slope_aspect  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsm", required=True)
    ap.add_argument("--out-dir", default="outputs/austin")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    slope, aspect, transform, crs = slope_aspect(args.dsm)

    with rasterio.open(args.dsm) as src:
        profile = src.profile
    profile.update(dtype="float32", count=1, nodata=-9999)

    for name, arr in [("slope_deg", slope), ("aspect_deg", aspect)]:
        out = os.path.join(args.out_dir, f"{name}.tif")
        a = np.where(np.isnan(arr), -9999, arr).astype("float32")
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(a, 1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
