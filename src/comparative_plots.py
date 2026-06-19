import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

a = gpd.read_file('austin.geojson')
k = gpd.read_file('kathmandu.geojson')

AUSTIN_C = '#2c7fb8'
KTM_C = '#d95f0e'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})

# FIGURE 1: distribution comparison (histogram + boxplot)
fig, axes = plt.subplots(1, 2, figsize=(12,4.5))

bins = np.linspace(0, 100000, 41)
axes[0].hist(a['annual_kwh'].clip(upper=100000), bins=bins, alpha=0.6, label=f'Austin (1 m LiDAR, n={len(a)})', color=AUSTIN_C, density=True)
axes[0].hist(k['annual_kwh'].clip(upper=100000), bins=bins, alpha=0.6, label=f'Kathmandu (30 m DSM, n={len(k)})', color=KTM_C, density=True)
axes[0].set_xlabel('Estimated annual rooftop solar (kWh)')
axes[0].set_ylabel('Density')
axes[0].set_title('Distribution of per-building solar potential\n(clipped at 100,000 kWh for visibility)')
axes[0].legend()
axes[0].xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{int(x/1000)}k'))

bp = axes[1].boxplot([a['annual_kwh'], k['annual_kwh']], labels=['Austin\n(1 m LiDAR)','Kathmandu\n(30 m DSM)'],
                     showfliers=False, patch_artist=True, widths=0.5)
for patch,c in zip(bp['boxes'],[AUSTIN_C,KTM_C]):
    patch.set_facecolor(c); patch.set_alpha(0.6)
axes[1].set_ylabel('Estimated annual rooftop solar (kWh)')
axes[1].set_title('Per-building solar potential\n(outliers hidden)')
axes[1].yaxis.set_major_formatter(FuncFormatter(lambda y,_:f'{int(y/1000)}k'))
plt.tight_layout()
plt.savefig('fig1_distributions.png', dpi=160, bbox_inches='tight')
plt.close()

# FIGURE 2: the smoking gun -- slope and usable fraction
fig, axes = plt.subplots(1, 3, figsize=(14,4.2))

axes[0].hist(a['mean_slope_deg'], bins=30, alpha=0.6, color=AUSTIN_C, label='Austin', density=True)
axes[0].hist(k['mean_slope_deg'], bins=30, alpha=0.6, color=KTM_C, label='Kathmandu', density=True)
axes[0].axvline(a['mean_slope_deg'].mean(), color=AUSTIN_C, ls='--', lw=1)
axes[0].axvline(k['mean_slope_deg'].mean(), color=KTM_C, ls='--', lw=1)
axes[0].set_xlabel('Mean roof slope (degrees)')
axes[0].set_ylabel('Density')
axes[0].set_title('Roof slope: LiDAR sees pitch,\ncoarse DSM flattens it')
axes[0].legend()

axes[1].hist(a['frac_under_slope_cap'], bins=30, alpha=0.6, color=AUSTIN_C, label='Austin', density=True)
axes[1].hist(k['frac_under_slope_cap'], bins=30, alpha=0.6, color=KTM_C, label='Kathmandu', density=True)
axes[1].set_xlabel('Fraction of roof under slope cap (usable)')
axes[1].set_ylabel('Density')
axes[1].set_title('Usable roof fraction:\ncoarse DSM marks ~all area usable')
axes[1].legend()

# survival rate bar
cities=['Austin\n(1 m LiDAR)','Kathmandu\n(30 m DSM)']
fetched=[1795,7290]; analyzed=[1728,947]
x=np.arange(2)
axes[2].bar(x-0.2,fetched,0.4,label='OSM footprints fetched',color='#bbbbbb')
axes[2].bar(x+0.2,analyzed,0.4,label='Buildings analyzed',color=[AUSTIN_C,KTM_C])
for i,(f,an) in enumerate(zip(fetched,analyzed)):
    axes[2].text(i+0.2,an+150,f'{100*an/f:.0f}%',ha='center',fontweight='bold')
axes[2].set_xticks(x); axes[2].set_xticklabels(cities)
axes[2].set_ylabel('Building count')
axes[2].set_title('Footprint survival:\ncoarse data discards small buildings')
axes[2].legend()
plt.tight_layout()
plt.savefig('fig2_resolution_bias.png', dpi=160, bbox_inches='tight')
plt.close()

print("Saved fig1_distributions.png, fig2_resolution_bias.png")
