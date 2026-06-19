import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from solar_suitability import building_suitability

SRC_DSM = "data/kathmandu/output_hh.tif"
DSM_UTM = "data/kathmandu/dsm_utm45n.tif"
OUT_FP = "outputs/Kathmandu/osm_footprints.geojson"
OUT_SOLAR = "outputs/Kathmandu/buildings_solar.geojson"

DST_EPSG = 32645
KATHMANDU_GHI = 1800.0

BBOX_S, BBOX_W = 27.687953, 85.310391
BBOX_N, BBOX_E = 27.700265, 85.333394


def reproject_to_utm(src_path, dst_path, dst_epsg):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, f"EPSG:{dst_epsg}", src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({
            "crs": f"EPSG:{dst_epsg}",
            "transform": transform,
            "width": width,
            "height": height,
            "nodata": -9999,
        })
        with rasterio.open(dst_path, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=f"EPSG:{dst_epsg}",
                    resampling=Resampling.bilinear,
                )
    print(f"Reprojected -> {dst_path} (EPSG:{dst_epsg})")


def main():
    os.makedirs("outputs/Kathmandu", exist_ok=True)
    reproject_to_utm(SRC_DSM, DSM_UTM, DST_EPSG)

    import osmnx as ox
    print("Fetching OSM building footprints for Kathmandu...")
    try:
        fp = ox.features_from_bbox(
            bbox=(BBOX_W, BBOX_S, BBOX_E, BBOX_N), tags={"building": True}
        )
    except TypeError:
        fp = ox.features_from_bbox(BBOX_N, BBOX_S, BBOX_E, BBOX_W, {"building": True})

    fp = fp[fp.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    fp = fp.to_crs(epsg=DST_EPSG)
    fp[[c for c in ["building", "geometry"] if c in fp.columns]].to_file(
        OUT_FP, driver="GeoJSON"
    )
    print(f"  {len(fp)} footprints -> {OUT_FP}")

    result = building_suitability(
        footprints_path=OUT_FP,
        dsm_path=DSM_UTM,
        out_path=OUT_SOLAR,
        annual_ghi_kwh_m2=KATHMANDU_GHI,
        max_slope_deg=45.0,
    )

    print("\n=== Kathmandu rooftop solar summary (footprint-level screen) ===")
    print(f"Buildings analysed: {len(result)}")
    if len(result):
        print(f"Total estimated annual kWh: {result['annual_kwh'].sum():,.0f}")
        print(f"Median per building: {result['annual_kwh'].median():,.0f} kWh")
        print(f"Top building: {result['annual_kwh'].max():,.0f} kWh")
    print(f"\nWrote {OUT_SOLAR}")
    print("NOTE: 30 m DSM cannot resolve roof planes; treat as a screen, not design.")


if __name__ == "__main__":
    main()