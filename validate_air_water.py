import sys, pandas as pd
sys.path.insert(0,'.')
from common import load
import bay_discharge as bd
base=load()
out=[]
for name,f in [('ERA5 (paper)',None),('Fort Point 9414290','data/validation/coops_9414290.csv'),('Alameda 9414750','data/validation/coops_9414750.csv'),('SFO','data/validation/sfo.csv')]:
    df=base.copy()
    if f:
        m=pd.read_csv(f,parse_dates=['time']); m['time']=m.time.dt.floor('h'); m=m.groupby('time').t.mean().reset_index()
        df=df.merge(m,on='time',how='left'); df['air_c']=df.t.fillna(df.air_c); df=df.drop(columns='t')
    h=bd.summarise(bd.run_hybrid_capped(df,21.0),'h'); s=bd.summarise(bd.seawater_first_capped(df,21.0),'s')
    out.append(dict(source=name,hybrid_m3=h['seawater_m3_per_yr'],sw_first_m3=s['seawater_m3_per_yr'],ratio=s['seawater_m3_per_yr']/h['seawater_m3_per_yr'],pump_runtime_pct=h.get('pump_runtime_pct',float('nan'))))
t=pd.DataFrame(out); print(t.round(1).to_string(index=False)); t.to_csv('results/air_validation_water.csv',index=False)
