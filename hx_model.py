"""Step 2: from Bay breeze to supply air - epsilon-NTU model of the two-stage heat exchanger chain.

For every hour, per cooling path (one per rack row):
  hot room return air --> Stage 1: air-to-air HX (outside marine air on the other side)
                      --> Stage 2: air-to-seawater coil (pumped only if Stage 1 is not enough)
                      --> Chiller trims whatever is left
                      --> supply air to the cold aisle at the setpoint.

Inputs are taken from the CFD Test 1 room model (270 kW, 2 paths, 10.06 m3/s room air per path,
33.25 C return air). Heat exchanger UA is fixed by a design effectiveness at design flows;
effectiveness then changes with the outside-air flow ratio via the NTU relations.
"""
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from common import load

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)

# ---- design inputs (per cooling path) -------------------------------------------------
Q_PATH = 135e3          # W, heat load per path (9 racks x 15 kW)
V_ROOM = 10.06          # m3/s room air per path
RHO, CP_AIR = 1.18, 1006.0
C_ROOM = V_ROOM * RHO * CP_AIR                 # W/K
T_RETURN = 33.25        # C, hot-aisle return air from CFD Test 1
SETPOINT = 21.0         # C, cold-aisle supply target
M_SEA, CP_SEA = 3.25, 3990.0                  # kg/s seawater per path (~51 GPM), J/kg-K
C_SEA = M_SEA * CP_SEA
EPS2_DESIGN = 0.80      # air-to-seawater coil effectiveness at design flows
CHILLER_COP = 5.0
PUMP_KW = 1.7           # per path (half of the 3.35 kW sized earlier for 1 MW-scale estimate)


def eps_crossflow_unmixed(ntu, cr):
    if cr < 1e-9:
        return 1 - math.exp(-ntu)
    return 1 - math.exp((1 / cr) * ntu**0.22 * (math.exp(-cr * ntu**0.78) - 1))


def eps_counterflow(ntu, cr):
    if abs(cr - 1) < 1e-9:
        return ntu / (1 + ntu)
    e = math.exp(-ntu * (1 - cr))
    return (1 - e) / (1 - cr * e)


def stage1_eps(eps_design, ratio):
    """UA fixed at design (ratio 1.0); return effectiveness applied to the room-air stream."""
    ntu_d = brentq(lambda n: eps_crossflow_unmixed(n, 1.0) - eps_design, 1e-3, 50)
    ua = ntu_d * C_ROOM
    c_out = ratio * C_ROOM
    cmin, cmax = min(C_ROOM, c_out), max(C_ROOM, c_out)
    eps = eps_crossflow_unmixed(ua / cmin, cmin / cmax)
    return eps * cmin / C_ROOM          # effectiveness expressed on the room-air side


def stage2_eps():
    cmin, cmax = min(C_ROOM, C_SEA), max(C_ROOM, C_SEA)
    ntu = brentq(lambda n: eps_counterflow(n, cmin / cmax) - EPS2_DESIGN, 1e-3, 50)
    return eps_counterflow(ntu, cmin / cmax) * cmin / C_ROOM


def run(df, eps1_design=0.75, ratio=1.0, setpoint=SETPOINT):
    e1, e2 = stage1_eps(eps1_design, ratio), stage2_eps()
    t_out, t_sea = df.air_c.values, df.water_c.values
    after1 = T_RETURN - e1 * (T_RETURN - t_out)
    after1 = np.clip(after1, setpoint, T_RETURN)        # modulate to avoid overcooling; bypass if outside air is hotter than return
    need2 = after1 > setpoint + 1e-9
    after2 = np.where(need2, after1 - e2 * np.maximum(after1 - t_sea, 0), after1)
    after2 = np.maximum(after2, setpoint)
    need_ch = after2 > setpoint + 1e-9
    stage = np.where(~need2, "Air only", np.where(~need_ch, "Air + seawater", "Chiller trim"))
    chiller_w = C_ROOM * (after2 - setpoint)
    res = df[["time", "air_c", "water_c", "water_measured"]].copy()
    res["after_stage1_c"], res["after_stage2_c"], res["stage"] = after1, after2, stage
    res["chiller_kw_per_path"] = chiller_w / 1e3
    return res, e1, e2


def summarise(res):
    n = len(res)
    share = res.stage.value_counts(normalize=True).reindex(["Air only", "Air + seawater", "Chiller trim"]).fillna(0)
    chiller_kwh = res.chiller_kw_per_path.sum() * 2 / CHILLER_COP        # electrical, both paths
    pump_kwh = (res.stage != "Air only").sum() * PUMP_KW * 2
    years = n / 8760
    return {"air_only_%": 100 * share["Air only"], "seawater_%": 100 * share["Air + seawater"],
            "chiller_%": 100 * share["Chiller trim"],
            "pump_runtime_%": 100 * (res.stage != "Air only").mean(),
            "chiller_MWh_e_per_yr": chiller_kwh / 1e3 / years,
            "pump_MWh_e_per_yr": pump_kwh / 1e3 / years,
            "peak_chiller_kw_th": res.chiller_kw_per_path.max() * 2}


if __name__ == "__main__":
    df = load()
    base, e1, e2 = run(df)
    s = summarise(base)
    t_star = T_RETURN - (T_RETURN - SETPOINT) / e1
    print(f"Stage 1 effectiveness {e1:.3f}, Stage 2 {e2:.3f}")
    print(f"Air alone reaches {SETPOINT} C whenever outside air <= {t_star:.1f} C")
    for k, v in s.items():
        print(f"  {k:24s} {v:8.2f}")
    base.to_csv(OUT / "hourly_baseline.csv", index=False)

    rows = []
    for sp in (21.0, 24.0):
        for eps in (0.65, 0.75, 0.85):
            for ratio in (1.0, 1.5):
                r, a, _ = run(df, eps, ratio, sp)
                rows.append({"setpoint_c": sp, "eps1_design": eps, "outside_air_ratio": ratio,
                             "eps1_actual": round(a, 3), **{k: round(v, 2) for k, v in summarise(r).items()}})
    sens = pd.DataFrame(rows)
    sens.to_csv(OUT / "sensitivity.csv", index=False)
    print(sens[["setpoint_c", "eps1_design", "outside_air_ratio", "air_only_%", "seawater_%", "chiller_%", "chiller_MWh_e_per_yr"]].to_string(index=False))

    monthly = base.assign(month=base.time.dt.month).groupby("month").stage.value_counts(normalize=True).unstack().fillna(0) * 100
    monthly.round(2).to_csv(OUT / "monthly_stage_share.csv")
    print(monthly.round(1).to_string())
