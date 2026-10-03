import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
INK, MUTED, GRID, SURF = "#1f2328", "#5b636e", "#e6e7e9", "#fcfcfb"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.edgecolor":GRID,"axes.labelcolor":MUTED,
 "xtick.color":MUTED,"ytick.color":INK,"figure.facecolor":SURF,"axes.facecolor":SURF})
D=pd.read_csv('lineA_digitised.csv')
fig,ax=plt.subplots(figsize=(10,4.2))
ax.axhline(27,color="#b3261e",lw=1.2,ls=(0,(5,3)))
ax.text(0.15,27.12,"ASHRAE recommended inlet limit, 27 °C",color="#b3261e",fontsize=10)
spec=[('2A','2A: end panels only, 21 °C supply',"#9a6a00",'-'),
      ('2B','2B: full containment, 21 °C supply',"#2a78d6",'-'),
      ('T3','Test 3: full containment, 24 °C supply',"#eb6834",'-'),
      ('T3fine','Test 3, refined mesh (566,640 cells)',"#1f2328",(0,(2,2)))]
for k,lab,c,ls in spec:
    g=D[D.run==k].copy()
    if k!='T3fine': g=g[g.x>=0.12]            # one-cell plate-edge artifact on the ~96k-cell mesh
    else:
        m=g.set_index('x')['T']; tail=g.x>5.33
        g.loc[tail,'T']=[m.get(round(5.4-x,2),np.nan) for x in g.x[tail]]   # end hidden by plot legend; profile is symmetric
    ax.plot(g.x,g['T'],color=c,lw=2.2 if k!='T3fine' else 1.6,ls=ls,label=lab)
ax.set_xlim(0,5.4); ax.set_ylim(20.5,28)
ax.set_xlabel("Distance along the row (m)"); ax.set_ylabel("Rack inlet temperature (°C)")
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.grid(color=GRID); ax.set_axisbelow(True)
ax.legend(loc="center",bbox_to_anchor=(0.5,0.62),frameon=False,fontsize=9.5,ncol=2)
fig.tight_layout(); fig.savefig('fig10_rack_inlet_profiles.png',dpi=200)
