"""Can the Bay breeze push outdoor air through Stage 1 without fan power?

Wind pressure available at the intake: dP_w = Cp_net * 0.5 * rho * (U cos(theta))^2, where theta is the
angle between the wind and the intake normal (no credit when the wind blows from behind). The outdoor-air
system needs dP_sys(s) = dP_design * s^2 at fan speed s, so the fan supplies max(0, dP_sys - dP_w).
Hourly wind: NOAA CO-OPS stations 9414290 (San Francisco) and 9414750 (Alameda), 2022-2024.
Run: python wind_assist.py
"""
import io, time, urllib.request
import numpy as np, pandas as pd
from common import load, DATA
import energy_model as em
import hx_model as hx

OUT = DATA.parent / "results"
RHO = 1.18
STATIONS = {"9414290": "San Francisco", "9414750": "Alameda"}


def fetch(st):
    f = DATA / "validation" / f"wind_{st}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["time"])
    parts = []
    for y in (2022, 2023, 2024):
        for m in range(1, 13):
            b = pd.Timestamp(y, m, 1); e = b + pd.offsets.MonthEnd(0)
            u = ("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=wind&application=research"
                 f"&station={st}&begin_date={b:%Y%m%d}&end_date={e:%Y%m%d}&time_zone=gmt&units=metric&interval=h&format=csv")
            for _ in range(3):
                try:
                    t = urllib.request.urlopen(u, timeout=60).read().decode(); break
                except Exception:
                    time.sleep(3); t = ""
            if t.startswith("Date"):
                d = pd.read_csv(io.StringIO(t)); d.columns = [c.strip() for c in d.columns]
                parts.append(pd.DataFrame({"time": pd.to_datetime(d["Date Time"]), "u": d["Speed"],
                                           "dir": d.iloc[:, 2]}))
    w = pd.concat(parts).drop_duplicates("time")
    w.to_csv(f, index=False)
    return w


def assist(res, a, w, cp_net, heading):
    """Outdoor-fan energy with wind assist. heading = direction the intake faces (deg, wind FROM)."""
    dp_des = a["dp_filters"] + a["dp_intake"] + a["dp_stage1_out"] + a["dp_exhaust"]
    design_kw = em.outdoor_fan_design_kw(a, 1.0) * em.N_PATHS
    s = (res.outdoor_fan_kw / design_kw).clip(lower=0) ** (1 / 3)          # recover speed from fan law
    m = res[["time"]].merge(w, on="time", how="left")
    u = m.u.fillna(m.u.median()).values
    th = np.radians(((m.dir.fillna(heading).values - heading + 180) % 360) - 180)
    un = np.where(np.abs(th) < np.pi / 2, u * np.cos(th), 0.0)
    dpw = cp_net * 0.5 * RHO * un ** 2
    need = dp_des * s ** 2
    fan_dp = np.clip(need - dpw, 0, None)
    flow = em.hx.V_ROOM * s * em.N_PATHS
    kw = flow * fan_dp / a["fan_eff"] / 1e3
    on = s > 0
    return {"outdoor_fan_MWh": res.outdoor_fan_kw.sum() / 1e3 / 3, "assisted_MWh": kw.sum() / 1e3 / 3,
            "hours_wind_alone_pct": 100 * ((need <= dpw) & on).sum() / on.sum(),
            "mean_wind_dp_Pa": dpw[on].mean(), "mean_need_Pa": need[on].mean(), "dp_design_Pa": dp_des}


if __name__ == "__main__":
    df = load()
    a = dict(em.A); a["dp_stage1_room"] = a["dp_stage1_out"] = 67      # sized plain-plate core
    res = em.hybrid(df, a=a, coil_bypass=True)
    tot = (res.room_fan_kw + res.outdoor_fan_kw + res.pump_kw + res.chiller_kw_e).sum() / 1e3 / 3
    rows = []
    for st, name in STATIONS.items():
        w = fetch(st)
        hours = w.time.dt.year.isin([2022, 2023, 2024]).sum()
        # prevailing direction (wind FROM), weighted by u^2
        rad = np.radians(w.dir.dropna()); wt = w.u[w.dir.notna()] ** 2
        prev = (np.degrees(np.arctan2((np.sin(rad) * wt).sum(), (np.cos(rad) * wt).sum())) + 360) % 360
        for cp in (0.5, 1.0):
            r = assist(res, a, w, cp, prev)
            r.update(station=name, cp_net=cp, prevailing_from_deg=round(prev), mean_u=w.u.mean(),
                     hours=hours, total_cooling_MWh=tot,
                     saved_MWh=r["outdoor_fan_MWh"] - r["assisted_MWh"])
            rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "wind_assist.csv", index=False)
    print(t.round(2).to_string())
