"""
Austin run: fetch OSM building footprints for the DSM extent and estimate
per-building rooftop solar potential. Produces:
  outputs/Austin/osm_footprints.geojson
  outputs/Austin/buildings_solar.geojson

Run from the project root:
    python src/run_austin.py
"""

import os
import sys

import geopandas as gpd
import rasterio
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from solar_suitability import building_suitability  # noqa: E402

DSM = "outputs/Austin/dsm.tif"
OUT_FP = "outputs/Austin/osm_footprints.geojson"
OUT_SOLAR = "outputs/Austin/buildings_solar.geojson"
AUSTIN_GHI = 1700.0  # placeholder; replace with cited Global Solar Atlas value


def main():
    # 1. Read DSM extent + CRS
    with rasterio.open(DSM) as src:
        bounds = src.bounds
        crs = src.crs
    print(f"DSM CRS: {crs}  (expecting EPSG:6343)")

    # 2. Build an AOI polygon in the DSM CRS, convert to lat/lon for OSM query
    aoi = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=crs).to_crs(4326)
    w, s, e, n = aoi.total_bounds
    print(f"AOI bbox (lon/lat): W={w:.5f} S={s:.5f} E={e:.5f} N={n:.5f}")

    # 3. Fetch OSM building footprints
    import osmnx as ox
    print("Fetching OSM building footprints...")
    try:
        # osmnx 2.x signature
        fp = ox.features_from_bbox(bbox=(w, s, e, n), tags={"building": True})
    except TypeError:
        # older signature fallback
        fp = ox.features_from_bbox(n, s, e, w, {"building": True})

    fp = fp[fp.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    fp = fp.to_crs(crs)
    fp[[c for c in ["building", "geometry"] if c in fp.columns]].to_file(
        OUT_FP, driver="GeoJSON"
    )
    print(f"  {len(fp)} footprints -> {OUT_FP}")

    # 4. Per-building suitability + energy estimate
    result = building_suitability(
        footprints_path=OUT_FP,
        dsm_path=DSM,
        out_path=OUT_SOLAR,
        annual_ghi_kwh_m2=AUSTIN_GHI,
        max_slope_deg=35.0,
    )

    # 5. Quick summary
    print("\n=== Austin rooftop solar summary ===")
    print(f"Buildings analysed: {len(result)}")
    print(f"Total estimated annual kWh: {result['annual_kwh'].sum():,.0f}")
    print(f"Median per building: {result['annual_kwh'].median():,.0f} kWh")
    print(f"Top building: {result['annual_kwh'].max():,.0f} kWh")
    print(f"\nWrote {OUT_SOLAR}")


if __name__ == "__main__":
    main()