"""Step 3: does it actually save energy? Fan + pump + chiller power and mechanical PUE.

Builds on hx_model.py (same hourly weather/water data and the same epsilon-NTU chain) and adds
the parasitic power the cooling system needs to run:

  * Room-air fans   - move 10.06 m3/s per path through ducts, both exchangers and the room, 24/7.
  * Outdoor-air fans - pull marine air through filters and the Stage 1 exchanger. Variable speed:
                       at each hour they run only as fast as needed to hit the setpoint
                       (fan power ~ speed^3), with a 20 % minimum speed.
  * Seawater pump   - only in hours when Stage 1 alone is not enough.
  * Chiller         - trims whatever is left (COP 5).

Mechanical PUE = (IT + cooling power) / IT. Electrical losses (UPS, lighting) are excluded and
flagged in the text; they are the same for every option compared here.

Two baselines use the same 270 kW room and the same room-air flow:
  * Chiller only - air-cooled chiller + CRAH coil every hour (no free cooling).
  * Seawater first - seawater coil every hour, chiller trim; no air stage (the conventional
    "use the Bay" design). Shows what the air stage buys in pump runtime and fouling exposure.

All pressure drops and efficiencies are typical design values (see ASSUMPTIONS below) and are
varied in the sensitivity table. They are the main uncertainty until vendor data is available.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import hx_model as hx
from common import load

OUT = Path(__file__).parent / "results"
IT_KW = 270.0
N_PATHS = 2

# ---- ASSUMPTIONS (per path unless noted) ------------------------------------------------
A = {
    # room-air (process) loop, Pa
    "dp_room_ducts": 250,      # supply + return duct runs over the roof
    "dp_stage1_room": 200,     # plate/air-to-air HX, room side
    "dp_stage2_coil": 120,     # air-to-seawater coil (air always passes through it)
    "dp_room_misc": 110,       # containment, diffusers, dampers, return filter (MERV 8)
    # outdoor-air (scavenger) loop at design flow, Pa
    "dp_filters": 150,         # MERV 13 bank, mid-life average
    "dp_intake": 100,          # louvers + intake manifold
    "dp_stage1_out": 200,      # HX, outdoor side
    "dp_exhaust": 100,         # plenum + exhaust
    "fan_eff": 0.60,           # fan x motor x VFD, total
    "min_speed": 0.20,         # outdoor-air fan minimum speed fraction
    # seawater pump
    "sea_head_kpa": 160,       # lift to deck (~5 m) + coil + strainer + pipe friction
    "pump_eff": 0.60,
    # baselines
    "chiller_cop_hybrid": hx.CHILLER_COP,   # trim chiller in the hybrid
    "chiller_cop_aircooled": 4.0,           # air-cooled chiller incl. condenser fans (baseline)
    "dp_crah_coil": 150,       # chilled-water coil replacing both exchangers in the baseline
}

RHO_SEA = 1025.0


def room_fan_kw(a):
    dp = a["dp_room_ducts"] + a["dp_stage1_room"] + a["dp_stage2_coil"] + a["dp_room_misc"]
    return hx.V_ROOM * dp / a["fan_eff"] / 1e3


def outdoor_fan_design_kw(a, ratio):
    dp = a["dp_filters"] + a["dp_intake"] + a["dp_stage1_out"] + a["dp_exhaust"]
    return ratio * hx.V_ROOM * dp / a["fan_eff"] / 1e3


def pump_kw(a):
    return hx.M_SEA / RHO_SEA * a["sea_head_kpa"] * 1e3 / a["pump_eff"] / 1e3


def speed_needed(t_out, eps1_design, ratio_max, setpoint):
    """Fraction of design outdoor-air flow needed for Stage 1 alone to reach the setpoint."""
    if t_out >= hx.T_RETURN:
        return 0.0                                  # outside air hotter than return: Stage 1 off
    e_req = (hx.T_RETURN - setpoint) / (hx.T_RETURN - t_out)
    if hx.stage1_eps(eps1_design, ratio_max) <= e_req:
        return 1.0                                  # full speed, Stage 2 picks up the rest
    f = lambda s: hx.stage1_eps(eps1_design, max(s, 1e-3) * ratio_max) - e_req
    return brentq(f, 1e-3, 1.0)


def hybrid(df, a=A, eps1_design=0.75, ratio=1.0, setpoint=hx.SETPOINT, coil_bypass=False):
    res, e1, e2 = hx.run(df, eps1_design, ratio, setpoint)
    # outdoor fan speed per hour (cache on rounded temperature: speed only depends on t_out)
    cache = {}
    def sp(t):
        k = round(float(t), 1)
        if k not in cache:
            cache[k] = max(speed_needed(k, eps1_design, ratio, setpoint), 0.0)
        return cache[k]
    speed = np.array([sp(t) for t in res.air_c.values])
    speed = np.where(speed > 0, np.maximum(speed, a["min_speed"]), 0.0)
    base_fan = room_fan_kw(a)
    if coil_bypass:   # room air skips the seawater coil (bypass damper) whenever the pump is off
        bypass_saving = hx.V_ROOM * a["dp_stage2_coil"] / a["fan_eff"] / 1e3
        res["room_fan_kw"] = np.where(res.stage == "Air only", base_fan - bypass_saving, base_fan) * N_PATHS
    else:
        res["room_fan_kw"] = base_fan * N_PATHS
    res["outdoor_fan_kw"] = outdoor_fan_design_kw(a, ratio) * speed**3 * N_PATHS
    res["pump_kw"] = np.where(res.stage != "Air only", pump_kw(a) * N_PATHS, 0.0)
    res["chiller_kw_e"] = res.chiller_kw_per_path * N_PATHS / a["chiller_cop_hybrid"]
    res["heat_to_bay_kw"] = np.where(res.stage != "Air only",
                                     hx.C_ROOM * (res.after_stage1_c - res.after_stage2_c) / 1e3 * N_PATHS, 0.0)
    return res


def chiller_only(df, a=A):
    dp = a["dp_room_ducts"] + a["dp_crah_coil"] + a["dp_room_misc"]
    res = df[["time"]].copy()
    res["room_fan_kw"] = hx.V_ROOM * dp / a["fan_eff"] / 1e3 * N_PATHS
    res["outdoor_fan_kw"] = 0.0
    res["pump_kw"] = 0.0
    res["chiller_kw_e"] = IT_KW / a["chiller_cop_aircooled"]
    return res


def seawater_first(df, a=A, setpoint=hx.SETPOINT):
    e2 = hx.stage2_eps()
    after = hx.T_RETURN - e2 * np.maximum(hx.T_RETURN - df.water_c.values, 0)
    after = np.maximum(after, setpoint)
    dp = a["dp_room_ducts"] + a["dp_stage2_coil"] + a["dp_room_misc"]
    res = df[["time"]].copy()
    res["room_fan_kw"] = hx.V_ROOM * dp / a["fan_eff"] / 1e3 * N_PATHS
    res["outdoor_fan_kw"] = 0.0
    res["pump_kw"] = pump_kw(a) * N_PATHS
    res["chiller_kw_e"] = hx.C_ROOM * (after - setpoint) / 1e3 * N_PATHS / a["chiller_cop_hybrid"]
    res["heat_to_bay_kw"] = hx.C_ROOM * (hx.T_RETURN - after) / 1e3 * N_PATHS
    return res


COMP = ["room_fan_kw", "outdoor_fan_kw", "pump_kw", "chiller_kw_e"]


def annual(res):
    years = len(res) / 8760
    mwh = {c: res[c].sum() / 1e3 / years for c in COMP}
    cool = sum(mwh.values())
    it = IT_KW * 8760 / 1e3
    out = {f"{c.replace('_kw_e', '').replace('_kw', '')}_MWh": v for c, v in mwh.items()}
    out["cooling_MWh"] = cool
    out["mech_PUE"] = 1 + cool / it
    out["pump_runtime_%"] = 100 * (res.pump_kw > 0).mean()
    out["seawater_1000m3_per_yr"] = (res.pump_kw > 0).sum() * 3600 * hx.M_SEA * N_PATHS / RHO_SEA / 1e3 / years
    out["heat_to_bay_MWh_th"] = res.get("heat_to_bay_kw", pd.Series(0.0, index=res.index)).sum() / 1e3 / years
    return out


if __name__ == "__main__":
    df = load()
    print("Per-path design power:  room fans %.1f kW, outdoor fans %.1f kW, pump %.2f kW"
          % (room_fan_kw(A), outdoor_fan_design_kw(A, 1.0), pump_kw(A)))

    runs = {"Hybrid (breeze first)": hybrid(df),
            "Hybrid + coil bypass": hybrid(df, coil_bypass=True),
            "Seawater first": seawater_first(df),
            "Chiller only": chiller_only(df)}
    table = pd.DataFrame({k: annual(v) for k, v in runs.items()}).T
    table.to_csv(OUT / "energy_comparison.csv")
    print(table.round(2).to_string())
    base = table.loc["Chiller only", "cooling_MWh"]
    for k in table.index:
        print(f"  {k:24s} cooling energy {table.loc[k, 'cooling_MWh']:7.1f} MWh/yr "
              f"({100 * (1 - table.loc[k, 'cooling_MWh'] / base):5.1f} % below chiller only), "
              f"mech. PUE {table.loc[k, 'mech_PUE']:.3f}")

    # monthly mechanical PUE for the hybrid
    h = runs["Hybrid (breeze first)"]
    h["cool_kw"] = h[COMP].sum(axis=1)
    monthly = h.assign(month=h.time.dt.month).groupby("month")[COMP + ["cool_kw"]].mean()
    monthly["mech_PUE"] = 1 + monthly.cool_kw / IT_KW
    monthly.round(3).to_csv(OUT / "monthly_energy_hybrid.csv")
    h.to_csv(OUT / "hourly_energy_hybrid.csv", index=False)

    # sensitivity: design choices and the uncertain pressure-drop / efficiency assumptions
    rows = []
    def add(label, **kw):
        a = dict(A); a.update(kw.pop("a", {}))
        r = annual(hybrid(df, a=a, **kw))
        rows.append({"case": label, **{k: round(v, 3) for k, v in r.items()}})
    add("Baseline (eps 0.75, ratio 1.0, 21 C)")
    add("Supply 24 C", setpoint=24.0)
    add("Outdoor-air ratio 1.5", ratio=1.5)
    add("Stage 1 eps 0.65", eps1_design=0.65)
    add("Stage 1 eps 0.85", eps1_design=0.85)
    add("All pressure drops +30 %", a={k: A[k] * 1.3 for k in A if k.startswith("dp_")})
    add("All pressure drops -30 %", a={k: A[k] * 0.7 for k in A if k.startswith("dp_")})
    add("Fan efficiency 0.50", a={"fan_eff": 0.50})
    add("Fan efficiency 0.70", a={"fan_eff": 0.70})
    add("Pump head 250 kPa", a={"sea_head_kpa": 250})
    sens = pd.DataFrame(rows)
    sens.to_csv(OUT / "energy_sensitivity.csv", index=False)
    print(sens[["case", "cooling_MWh", "mech_PUE", "pump_runtime_%"]].to_string(index=False))

    # chiller-only baseline sensitivity to COP (a fair comparison needs this)
    for cop in (3.0, 4.0, 5.0, 6.0):
        a = dict(A); a["chiller_cop_aircooled"] = cop
        r = annual(chiller_only(df, a))
        print(f"  chiller-only COP {cop}: {r['cooling_MWh']:.0f} MWh/yr, mech PUE {r['mech_PUE']:.3f}")
