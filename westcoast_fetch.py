import urllib.request, io, pandas as pd, numpy as np, time, os, sys
B={"San Diego (La Jolla)":"LJPC1","Santa Monica Bay, LA":"46025","Santa Maria / Morro Bay":"46011","Monterey Bay":"46042",
"Half Moon Bay":"46012","San Francisco offshore":"46026","Bodega Bay / Pt Reyes":"46013","Point Arena":"46014","Humboldt / Eureka":"46022",
"Crescent City (St George)":"46027","Port Orford / Coos Bay, OR":"46015","Newport, OR":"46050","Astoria (Columbia R.), OR":"46029",
"Westport (Cape Elizabeth), WA":"46041","Neah Bay, WA":"46087"}
def year(st,y):
    u=f"https://www.ndbc.noaa.gov/view_text_file.php?filename={st.lower()}h{y}.txt.gz&dir=data/historical/stdmet/"
    for k in range(4):
        try:
            with urllib.request.urlopen(u,timeout=120) as r: t=r.read().decode()
            break
        except Exception as e: print(' retry',st,y,e); time.sleep(5)
    else: return None
    L=[l for l in t.splitlines() if l and not l.startswith('#')]
    if not L: return None
    hdr=t.splitlines()[0].lstrip('#').split()
    df=pd.read_csv(io.StringIO("\n".join(L)),sep=r"\s+",header=None,names=hdr)
    df["time"]=pd.to_datetime(dict(year=df.iloc[:,0],month=df.MM,day=df.DD,hour=df.hh))
    out=df[["time","WSPD","ATMP","WTMP"]].astype({"WSPD":float,"ATMP":float,"WTMP":float})
    for c in ["WSPD","ATMP","WTMP"]: out.loc[out[c]>=99,c]=np.nan
    return out
meta={}
for name,st in B.items():
    fn=f"data/westcoast/b_{st}.csv"
    if os.path.exists(fn): continue
    parts=[p for y in (2022,2023,2024) if (p:=year(st,y)) is not None]
    if not parts: print('NO DATA',name); continue
    d=pd.concat(parts); d["time"]=d.time.dt.floor("h"); d=d.groupby("time").mean().reset_index()
    d.to_csv(fn,index=False)
    print(f"{name:32s} {st} n={len(d)} air={d.ATMP.notna().mean():.2f} water={d.WTMP.notna().mean():.2f} wind={d.WSPD.notna().mean():.2f}")
