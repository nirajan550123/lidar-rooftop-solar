import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats
import json

a = gpd.read_file('austin.geojson')
k = gpd.read_file('kathmandu.geojson')

# OSM footprints fetched (from run logs): Austin 1795, Kathmandu 7290
FETCHED = {'Austin': 1795, 'Kathmandu': 7290}

def describe(g, name):
    s = g['annual_kwh']
    fp = g['footprint_m2']
    return {
        'city': name,
        'analyzed': len(g),
        'fetched': FETCHED[name],
        'survival_pct': round(100*len(g)/FETCHED[name],1),
        'total_kwh': float(s.sum()),
        'mean_kwh': float(s.mean()),
        'median_kwh': float(s.median()),
        'std_kwh': float(s.std()),
        'min_kwh': float(s.min()),
        'max_kwh': float(s.max()),
        'q25_kwh': float(s.quantile(.25)),
        'q75_kwh': float(s.quantile(.75)),
        'mean_footprint_m2': float(fp.mean()),
        'median_footprint_m2': float(fp.median()),
        'mean_slope': float(g['mean_slope_deg'].mean()),
        'mean_aspect_score': float(g['aspect_score'].mean()),
        'mean_frac_usable': float(g['frac_under_slope_cap'].mean()),
    }

da, dk = describe(a,'Austin'), describe(k,'Kathmandu')

print("="*60)
for d in (da, dk):
    print(f"\n{d['city']}:")
    for key,v in d.items():
        if key!='city':
            print(f"  {key}: {v:,.1f}" if isinstance(v,float) else f"  {key}: {v}")

# Statistical tests comparing the two distributions
u_stat, u_p = stats.mannwhitneyu(a['annual_kwh'], k['annual_kwh'], alternative='two-sided')
ks_stat, ks_p = stats.ks_2samp(a['annual_kwh'], k['annual_kwh'])

print("\n" + "="*60)
print("DISTRIBUTION TESTS (annual_kwh):")
print(f"  Mann-Whitney U: U={u_stat:,.0f}, p={u_p:.3e}")
print(f"  Kolmogorov-Smirnov: D={ks_stat:.3f}, p={ks_p:.3e}")

# Footprint-size correlation with kwh
for g,name in [(a,'Austin'),(k,'Kathmandu')]:
    r = np.corrcoef(g['footprint_m2'], g['annual_kwh'])[0,1]
    print(f"  {name} footprint-vs-kwh Pearson r: {r:.3f}")

# Slope comparison: does coarse DSM flatten roofs?
print("\nSLOPE (coarse DSM should look flatter):")
print(f"  Austin mean slope: {da['mean_slope']:.1f} deg")
print(f"  Kathmandu mean slope: {dk['mean_slope']:.1f} deg")
print(f"  Austin mean aspect score: {da['mean_aspect_score']:.3f}")
print(f"  Kathmandu mean aspect score: {dk['mean_aspect_score']:.3f}")
print(f"  Austin frac usable: {da['mean_frac_usable']:.3f}")
print(f"  Kathmandu frac usable: {dk['mean_frac_usable']:.3f}")

json.dump({'austin':da,'kathmandu':dk,
           'tests':{'mannwhitney_p':float(u_p),'ks_D':float(ks_stat),'ks_p':float(ks_p)}},
          open('stats.json','w'), indent=2)
print("\nSaved stats.json")
