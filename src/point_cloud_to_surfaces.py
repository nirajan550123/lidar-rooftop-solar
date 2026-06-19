"""
Step 1 (Austin / LiDAR side): turn a raw 3DEP LAZ tile into a DSM and a DTM.

DSM = digital surface model (first returns; tops of roofs, trees, etc.)
DTM = digital terrain model (ground returns only; bare earth)

We use PDAL pipelines because they are reproducible, declarative, and the
standard tool for production point-cloud work. Each pipeline is just JSON, so
the exact processing is auditable in the repo (which is your differentiator).

Usage:
    python src/point_cloud_to_surfaces.py \
        --laz data/austin/tile.laz \
        --out-dir outputs/austin \
        --resolution 1.0 \
        --epsg 6578   # NAD83(2011) / Texas Central (meters) -- VERIFY for your tile
"""

import argparse
import json
import os
import subprocess


def run_pdal_pipeline(pipeline: dict) -> None:
    """Execute a PDAL pipeline passed as a Python dict."""
    proc = subprocess.run(
        ["pdal", "pipeline", "--stdin"],
        input=json.dumps(pipeline).encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"PDAL pipeline failed:\n{proc.stderr.decode('utf-8', errors='replace')}"
        )


def inspect(laz_path: str) -> None:
    """Print a quick metadata summary so you can confirm CRS, bounds, point count."""
    proc = subprocess.run(
        ["pdal", "info", "--summary", laz_path],
        capture_output=True,
    )
    print(proc.stdout.decode("utf-8", errors="replace"))


def build_dsm(laz_path: str, out_tif: str, resolution: float, epsg: int) -> dict:
    """First-return surface. We keep the highest Z per cell to capture rooftops."""
    return {
        "pipeline": [
            laz_path,
            # Reproject into a projected, metre-based CRS so slope/area are in metres.
            {"type": "filters.reprojection", "out_srs": f"EPSG:{epsg}"},
            # Drop noise points that would create spurious high spikes.
            {"type": "filters.outlier", "method": "statistical",
             "mean_k": 8, "multiplier": 3.0},
            {"type": "filters.range", "limits": "Classification![7:7]"},
            # max Z per cell -> surface tops.
            {"type": "writers.gdal", "filename": out_tif,
             "resolution": resolution, "output_type": "max",
             "nodata": -9999, "gdaldriver": "GTiff"},
        ]
    }


def build_dtm(laz_path: str, out_tif: str, resolution: float, epsg: int) -> dict:
    """Bare earth. Use ground-classified returns; if absent, run SMRF first."""
    return {
        "pipeline": [
            laz_path,
            {"type": "filters.reprojection", "out_srs": f"EPSG:{epsg}"},
            # If the tile is already ground-classified (3DEP usually is), this keeps
            # class 2. If yours is not, uncomment the SMRF filter below.
            # {"type": "filters.smrf"},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "writers.gdal", "filename": out_tif,
             "resolution": resolution, "output_type": "idw",
             "nodata": -9999, "gdaldriver": "GTiff"},
        ]
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--laz", required=True, help="Path to the 3DEP LAZ tile")
    ap.add_argument("--out-dir", default="outputs/austin")
    ap.add_argument("--resolution", type=float, default=1.0, help="Cell size in metres")
    ap.add_argument("--epsg", type=int, required=True,
                    help="Target projected EPSG (metres). Verify against your tile.")
    ap.add_argument("--skip-inspect", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    if not args.skip_inspect:
        print("=== Point cloud summary (confirm CRS + bounds match --epsg) ===")
        inspect(args.laz)

    dsm_path = os.path.join(args.out_dir, "dsm.tif")
    dtm_path = os.path.join(args.out_dir, "dtm.tif")

    print("Building DSM (first-return surface)...")
    run_pdal_pipeline(build_dsm(args.laz, dsm_path, args.resolution, args.epsg))
    print(f"  wrote {dsm_path}")

    print("Building DTM (bare earth)...")
    run_pdal_pipeline(build_dtm(args.laz, dtm_path, args.resolution, args.epsg))
    print(f"  wrote {dtm_path}")

    print("Done. Next: src/terrain_metrics.py to derive slope/aspect from the DSM.")


if __name__ == "__main__":
    main()
