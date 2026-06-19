"""
Kathmandu transfer side. No LiDAR exists openly for Nepal, so the surface comes
from an OPEN global DSM (Copernicus GLO-30 or AW3D30, ~30 m) and rooftops come
from OpenStreetMap. The SAME solar_suitability module that runs Austin runs here.
That is the methods-transfer thesis in code.

Honest limitations baked in:
  - A 30 m DSM cannot resolve individual roof planes. We therefore run a
    FOOTPRINT-LEVEL suitability screen, not per-facet optimisation, and the
    writeup says so plainly.
  - OSM footprint completeness in Kathmandu is strong in the urban core but
    weaker in peri-urban/informal areas, and footprint datasets disagree by
    ~50% in total area. We pick the urban core and note the sensitivity.

You provide:
  - data/kathmandu/dsm.tif  (download Copernicus GLO-30 for your AOI, reproject
    to a metric CRS e.g. EPSG:32645 UTM 45N, then drop it here)

This script:
  - pulls OSM building footprints for a Kathmandu bounding box via osmnx
  - reprojects to match the DSM
  - runs building_suitability() with Kathmandu GHI

Usage:
    python src/kathmandu_transfer.py \
        --dsm data/kathmandu/dsm.tif \
        --out outputs/kathmandu/buildings_solar.geojson \
        --bbox 27.69 85.30 27.73 85.34   # S W N E (small urban-core box)
"""

import argparse
import os
import sys

import geopandas as gpd

sys.path.insert(0, os.path.dirname(__file__))
from solar_suitability import building_suitability  # noqa: E402

KATHMANDU_GHI = 1800.0  # kWh/m2/yr, first-order. Replace with a cited value
                        # from Global Solar Atlas for your exact AOI before reporting.


def fetch_osm_buildings(bbox, out_path, metric_epsg=32645):
    """bbox = (south, west, north, east). Saves footprints as GeoJSON."""
    import osmnx as ox
    south, west, north, east = bbox
    tags = {"building": True}
    gdf = ox.features_from_bbox(north, south, east, west, tags)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    # Keep only useful columns; OSM has hundreds of sparse ones.
    keep = [c for c in ["building", "building:levels", "height", "name", "geometry"]
            if c in gdf.columns]
    gdf = gdf[keep].to_crs(epsg=metric_epsg)
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"Fetched {len(gdf)} OSM building footprints -> {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsm", required=True, help="Reprojected open DSM (metric CRS)")
    ap.add_argument("--out", default="outputs/kathmandu/buildings_solar.geojson")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("S", "W", "N", "E"),
                    help="Bounding box: south west north east (small urban-core box)")
    ap.add_argument("--metric-epsg", type=int, default=32645)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fp_path = os.path.join(os.path.dirname(args.out), "osm_footprints.geojson")

    fetch_osm_buildings(tuple(args.bbox), fp_path, args.metric_epsg)

    building_suitability(
        footprints_path=fp_path,
        dsm_path=args.dsm,
        out_path=args.out,
        annual_ghi_kwh_m2=KATHMANDU_GHI,
        # At 30 m the slope cap is generous: we are screening footprints, not facets.
        max_slope_deg=45.0,
    )
    print("Done. Compare outputs/kathmandu vs outputs/austin in your dashboard.")


if __name__ == "__main__":
    main()
