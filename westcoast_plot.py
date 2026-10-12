import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import cartopy.crs as ccrs, cartopy.feature as cf
INK,MUTED="#1f2328","#5b636e"
t=pd.read_csv("results/westcoast_sites.csv")
pc=ccrs.PlateCarree()
cmap=LinearSegmentedColormap.from_list("b",["#f2b36b","#9ec5f4","#2a78d6","#0b3d91"])
norm=Normalize(60,100)
fig=plt.figure(figsize=(8.2,10.6),facecolor="white")
ax=fig.add_axes([0.02,0.105,0.96,0.80],projection=pc)
ax.set_extent([-131.8,-116.2,31.8,49.4],crs=pc)
ax.add_feature(cf.LAND.with_scale("50m"),facecolor="#ecebe7",edgecolor="none",zorder=0)
ax.add_feature(cf.OCEAN.with_scale("50m"),facecolor="#f7fafd",zorder=0)
ax.add_feature(cf.COASTLINE.with_scale("50m"),linewidth=0.6,edgecolor="#8a8f96",zorder=1)
ax.add_feature(cf.STATES.with_scale("50m"),linewidth=0.4,edgecolor="#b8bcc2",zorder=1)
for _,r in t.iterrows():
    bay=r.site.startswith("SF Bay")
    ax.scatter(r.lon,r.lat,s=170 if bay else 120,c=[cmap(norm(r.breeze_only_pct))],marker="*" if bay else "o",edgecolors="white",linewidths=1.2,transform=pc,zorder=5)
    pct=("%.1f" % r.breeze_only_pct) if r.breeze_only_pct>=99 else ("%.0f" % r.breeze_only_pct)
    lab=f"{r.site}  {pct}%  ·  {r.wind_mean_ms:.1f} m/s"
    dx,dy,ha=(-0.45,0,"right")
    if bay: dx,dy,ha=(0.45,-0.35,"left"); lab="SF Bay pier (this paper)  85%"
    if r.site.startswith("Half Moon"): dy=-0.2
    if r.site.startswith("Bodega"): dy=0.15
    ax.text(r.lon+dx,r.lat+dy,lab,fontsize=8.6,color=INK,ha=ha,va="center",transform=pc,zorder=6,
            bbox=dict(boxstyle="round,pad=0.15",fc="white",ec="none",alpha=0.8))
for s,(x,y) in {"WASHINGTON":(-120.3,47.6),"OREGON":(-120.5,44.0),"CALIFORNIA":(-119.3,37.8)}.items():
    ax.text(x,y,s,fontsize=9,color=MUTED,ha="center",transform=pc)
cax=fig.add_axes([0.15,0.075,0.7,0.012])
cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,orientation="horizontal")
cb.set_label("Hours the outdoor-air stage alone holds 21 °C supply air (%)",color=MUTED,fontsize=9); cb.outline.set_visible(False); cb.ax.tick_params(colors=MUTED,labelsize=8)
fig.text(0.03,0.962,"Air-first cooling along the US West Coast",fontsize=14.5,weight="bold",color=INK)
fig.text(0.03,0.935,"Share of hours the outdoor air alone cools the 270 kW module, and mean wind speed.\nSame model as the paper, driven by measured NOAA buoy air and sea temperatures, 2022–2024.",fontsize=9.5,color=MUTED)
fig.text(0.03,0.01,"Buoys lie 6–55 nautical miles offshore; shoreline air is warmer, especially in Southern California. Gaps filled with month-hour climatology. \nSF Bay pier uses the paper's reanalysis air and tide-station water data.",fontsize=7,color=MUTED,wrap=True)
fig.savefig("results/fig_westcoast_sites.png",dpi=200)
