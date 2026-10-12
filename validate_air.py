import sys, pandas as pd, numpy as np
sys.path.insert(0,'.')
from common import load
import hx_model as hx
base=load()
era=base[['time','air_c']].drop_duplicates('time')
out=[]
srcs={'NOAA SF tide stn 9414290 (Fort Point)':'data/validation/coops_9414290.csv','NOAA Alameda 9414750':'data/validation/coops_9414750.csv','SFO airport (ASOS)':'data/validation/sfo.csv'}
res_era,_,_=hx.run(base)
def shares(r):
    v=r.stage.value_counts(normalize=True)*100
    return v.get('Air only',0),v.get('Air + seawater',0),v.get('Chiller trim',0)
a,b,c=shares(res_era)
rows=[dict(source='ERA5 reanalysis (paper)',hours=len(era),bias_K=np.nan,rmse_K=np.nan,r=np.nan,mean_C=era.air_c.mean(),p99_C=era.air_c.quantile(.99),pct_above_16_9=(era.air_c>16.9167).mean()*100,air_only=a,seawater=b,chiller=c)]
for name,f in srcs.items():
    m=pd.read_csv(f,parse_dates=['time'])
    m['time']=m.time.dt.floor('h'); m=m.groupby('time').t.mean().reset_index()
    j=era.merge(m,on='time',how='inner').dropna()
    d=j.t-j.air_c
    # run model with measured air (fill gaps with ERA5)
    df=base.copy().merge(m,on='time',how='left'); cov=df.t.notna().mean()*100
    df['air_c']=df.t.fillna(df.air_c)
    r,_,_=hx.run(df.drop(columns='t'))
    a,b,c=shares(r)
    rows.append(dict(source=name,hours=len(j),coverage_pct=cov,bias_K=d.mean(),rmse_K=np.sqrt((d**2).mean()),r=np.corrcoef(j.t,j.air_c)[0,1],
        mean_C=j.t.mean(),p99_C=j.t.quantile(.99),pct_above_16_9=(j.t>16.9167).mean()*100,air_only=a,seawater=b,chiller=c))
t=pd.DataFrame(rows); pd.set_option('display.width',250)
print(t.round(2).to_string(index=False)); t.round(3).to_csv('results/air_validation_summary.csv',index=False)
# seasonal bias for SF station
m=pd.read_csv('data/validation/coops_9414290.csv',parse_dates=['time']); m['time']=m.time.dt.floor('h'); m=m.groupby('time').t.mean().reset_index()
j=era.merge(m,on='time'); j['mo']=j.time.dt.month
print((j.groupby('mo').apply(lambda g:(g.t-g.air_c).mean())).round(2).to_string())
