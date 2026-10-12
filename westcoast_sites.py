import sys, pandas as pd, numpy as np
sys.path.insert(0,'.')
from common import load
import hx_model as hx, energy_model as em, bay_discharge as bd, hx_sizing as hs
sized=dict(em.A); d=hs.size_module(3e-3,1.2); sized["dp_stage1_room"]=sized["dp_stage1_out"]=d["dp_pa"]
idx=pd.DataFrame({"time":pd.date_range("2022-01-01","2024-12-31 23:00",freq="h")})
def rd(st): 
    x=pd.read_csv(f"data/westcoast/b_{st}.csv",parse_dates=["time"]); return x
def fill(s,t):
    k=pd.DataFrame({"m":t.dt.month,"h":t.dt.hour,"v":s.values})
    cl=k.groupby(["m","h"]).v.transform("mean"); return s.fillna(pd.Series(cl.values,index=s.index))
SITES=[("San Diego (offshore)",32.504,-118.029,"46086","46086","46086"),
("Los Angeles (Santa Monica)",33.765,-119.077,"46025","46025","46025"),
("Morro Bay (Cape San Martin)",35.763,-121.900,"46028","46028","46028"),
("Monterey",36.787,-122.408,"46042","46042","46042"),
("Half Moon Bay / SF offshore",37.356,-122.881,"46012","46026","46012"),
("Bodega Bay / Pt Reyes",38.235,-123.317,"46013","46013","46013"),
("Point Arena",39.225,-123.980,"46014","46014","46014"),
("Eureka (Humboldt)",40.716,-124.540,"46022","46022","46022"),
("Crescent City",41.840,-124.382,"46027","46027","46027"),
("Port Orford, OR",42.754,-124.839,"46015","46015","46015"),
("Newport, OR",44.679,-124.535,"46050","46050","46050"),
("Astoria, OR",46.148,-124.508,"46029","46029","46029"),
("Westport, WA",47.351,-124.741,"46041","46041","46041"),
("Neah Bay, WA",48.493,-124.727,"46087","46087","46087")]
FALLBACK={"46012":"46013","46015":"46027"}
rows=[]
def evaluate(name,lat,lon,df,wind,cov_a,cov_w):
    r,_,_=hx.run(df); v=r.stage.value_counts(normalize=True)*100
    e=bd.energy_compliant(df,sized); s=bd.seawater_first_energy_compliant(df,em.A)
    rows.append(dict(site=name,lat=lat,lon=lon,air_mean_C=df.air_c.mean(),air_p99_C=df.air_c.quantile(.99),water_mean_C=df.water_c.mean(),
        wind_mean_ms=wind,air_cov=cov_a,water_cov=cov_w,breeze_only_pct=v.get("Air only",0),seawater_pct=v.get("Air + seawater",0),chiller_pct=v.get("Chiller trim",0),
        hybrid_MWh=e["cooling_MWh"],hybrid_PUE=e["mech_PUE"],hybrid_water_m3=e["seawater_1000m3_per_yr"]*1e3,swf_MWh=s["cooling_MWh"],swf_water_m3=s["seawater_1000m3_per_yr"]*1e3))
for name,lat,lon,sa,sw,swd in SITES:
    A=rd(sa)[["time","ATMP"]]; W=rd(sw)[["time","WTMP"]]; V=rd(swd)[["time","WSPD"]]
    df=idx.merge(A,on="time",how="left").merge(W,on="time",how="left")
    ca,cw=df.ATMP.notna().mean(),df.WTMP.notna().mean()
    if sa in FALLBACK:
        fb=rd(FALLBACK[sa])[["time","ATMP"]].rename(columns={"ATMP":"fb"})
        df=df.merge(fb,on="time",how="left")
        # fill whole missing months from fallback
        mm=df.groupby(df.time.dt.month).ATMP.transform(lambda s:s.notna().any())
        df.loc[~mm,"ATMP"]=df.loc[~mm,"fb"]; df=df.drop(columns="fb")
    df["air_c"]=fill(df.ATMP,df.time); df["water_c"]=fill(df.WTMP,df.time)
    df["water_measured"]=True; df=df[["time","air_c","water_c","water_measured"]]
    evaluate(name,lat,lon,df,V.WSPD.mean(),ca,cw)
# paper Bay site
b=load(); evaluate("SF Bay pier (paper)",37.79,-122.35,b,np.nan,1,1)
t=pd.DataFrame(rows); t.to_csv("results/westcoast_sites.csv",index=False)
pd.set_option("display.width",300)
print(t[["site","air_mean_C","air_p99_C","water_mean_C","wind_mean_ms","air_cov","water_cov","breeze_only_pct","seawater_pct","chiller_pct","hybrid_MWh","hybrid_PUE","hybrid_water_m3","swf_MWh","swf_water_m3"]].round(2).to_string(index=False))
