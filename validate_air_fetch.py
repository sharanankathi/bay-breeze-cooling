import json, time, urllib.request, pandas as pd, io
def coops(st):
    rows=[]
    for y in (2022,2023,2024):
        for m in range(1,13):
            b=f"{y}{m:02d}01"; e=(pd.Timestamp(y,m,1)+pd.offsets.MonthEnd(0)).strftime("%Y%m%d")
            u=("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=air_temperature&application=research"
               f"&begin_date={b}&end_date={e}&station={st}&time_zone=lst_ldt&units=metric&interval=h&format=json")
            for k in range(3):
                try:
                    with urllib.request.urlopen(u,timeout=60) as r: rows+=json.load(r).get("data",[]); break
                except Exception as ex: time.sleep(2)
            time.sleep(0.2)
    df=pd.DataFrame(rows); df=df[df.v!=""]
    df=pd.DataFrame({"time":pd.to_datetime(df.t),"t":df.v.astype(float)}).drop_duplicates("time")
    df.to_csv(f"data/validation/coops_{st}.csv",index=False); print(st,len(df))
def sfo():
    u=("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=SFO&data=tmpf&year1=2022&month1=1&day1=1"
       "&year2=2025&month2=1&day2=1&tz=America%2FLos_Angeles&format=onlycomma&latlon=no&missing=empty&report_type=3")
    with urllib.request.urlopen(u,timeout=180) as r: txt=r.read().decode()
    df=pd.read_csv(io.StringIO(txt)); df=df.dropna(subset=["tmpf"])
    df["time"]=pd.to_datetime(df["valid"]); df["t"]=(df.tmpf-32)/1.8
    df[["time","t"]].to_csv("data/validation/sfo.csv",index=False); print("sfo",len(df))
coops("9414290"); coops("9414750"); sfo()
