"""
Shared back-half of the pipeline. This is the methods-transfer hinge: BOTH the
Austin (LiDAR DSM) and Kathmandu (open DSM) workflows call these same functions.
What changes between cities is the INPUT surface and its resolution, not the
analysis logic. That is exactly the story your portfolio writeup should tell.

Provides:
  - slope_aspect(dsm): degrees slope + aspect from any DSM raster
  - building_suitability(...): zonal stats per OSM footprint -> solar estimate

Solar note:
  True insolation modelling (sky-view, horizon shading, diffuse/direct split)
  is best done in ArcGIS Pro 'Area Solar Radiation' on the Austin 1 m DSM. This
  module computes the GEOMETRIC suitability layer (slope/aspect/area) and a
  first-order energy estimate so the Python pipeline is self-contained and
  reproducible. The writeup should be explicit about this split.
"""

import numpy as np
import rasterio
from rasterio.features import geometry_mask
import geopandas as gpd


def slope_aspect(dsm_path: str):
    """Return (slope_deg, aspect_deg, transform, crs) from a DSM raster."""
    with rasterio.open(dsm_path) as src:
        z = src.read(1).astype("float64")
        z[z == src.nodata] = np.nan
        px = src.res[0]
        py = src.res[1]
        transform = src.transform
        crs = src.crs

    # Horn (1981) 3x3 gradient, the same method ArcGIS uses.
    dzdx = np.gradient(z, axis=1) / px
    dzdy = np.gradient(z, axis=0) / py
    slope = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))

    aspect = np.degrees(np.arctan2(dzdy, -dzdx))
    aspect = np.where(aspect < 0, 90.0 - aspect,
                      np.where(aspect > 90.0, 360.0 - aspect + 90.0, 90.0 - aspect))
    return slope, aspect, transform, crs


def _aspect_score(aspect_deg, hemisphere="north"):
    """
    1.0 when roof faces the equator, falling off toward poleward.
    Northern hemisphere: best aspect = 180 (south). Both Austin and Kathmandu
    are northern, so south-facing is ideal for both.
    """
    ideal = 180.0
    diff = np.abs(((aspect_deg - ideal + 180.0) % 360.0) - 180.0)
    return np.clip(1.0 - diff / 180.0, 0.0, 1.0)


def building_suitability(
    footprints_path: str,
    dsm_path: str,
    out_path: str,
    max_slope_deg: float = 35.0,
    panel_efficiency: float = 0.20,
    performance_ratio: float = 0.75,
    annual_ghi_kwh_m2: float = 1700.0,  # site-specific; replace per city
    usable_fraction: float = 0.70,      # roof area actually mountable
):
    """
    Aggregate slope/aspect to each building footprint and estimate annual kWh.

    annual_ghi_kwh_m2: global horizontal irradiation for the city. Austin ~1700,
    Kathmandu ~1800 (verify from a real source before reporting numbers).

    Energy model (first-order, transparent):
        usable_area = footprint_area * usable_fraction * (frac cells under slope cap)
        yield = usable_area * GHI * aspect_score * efficiency * performance_ratio
    """
    slope, aspect, transform, crs = slope_aspect(dsm_path)
    gdf = gpd.read_file(footprints_path).to_crs(crs)

    out_height, out_width = slope.shape
    records = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        mask = geometry_mask(
            [geom], out_shape=(out_height, out_width),
            transform=transform, invert=True,
        )
        if not mask.any():
            continue

        s = slope[mask]
        a = aspect[mask]
        valid = ~np.isnan(s)
        if valid.sum() == 0:
            continue
        s, a = s[valid], a[valid]

        under_cap = s <= max_slope_deg
        frac_usable = float(under_cap.mean())
        mean_aspect_score = float(_aspect_score(a[under_cap]).mean()) if under_cap.any() else 0.0

        footprint_area = float(geom.area)  # m^2 in projected CRS
        usable_area = footprint_area * usable_fraction * frac_usable

        annual_kwh = (
            usable_area * annual_ghi_kwh_m2 * mean_aspect_score
            * panel_efficiency * performance_ratio
        )

        records.append({
            "geometry": geom,
            "footprint_m2": round(footprint_area, 1),
            "usable_m2": round(usable_area, 1),
            "mean_slope_deg": round(float(s.mean()), 1),
            "frac_under_slope_cap": round(frac_usable, 3),
            "aspect_score": round(mean_aspect_score, 3),
            "annual_kwh": round(annual_kwh, 0),
        })

    result = gpd.GeoDataFrame(records, crs=crs)
    result.to_file(out_path, driver="GeoJSON")
    print(f"Wrote {len(result)} buildings -> {out_path}")
    return result
