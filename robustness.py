"""Step 5b: robustness checks that do not need new CAD or CFD.

  1. Fan heat. Room-air fans run 24/7 and their power ends up as heat in the room-air loop.
     Compare it with the heat the model already removes (the CFD return temperature implies
     about 292 kW for a 270 kW IT load).
  2. Fouling of the outdoor side of the Stage 1 plate exchanger (salt and dust deposits).
     In laminar channels the deposit's thermal resistance is small; the real penalty is that it
     narrows the gap, and laminar pressure drop scales with 1/gap^3.
  3. Condensation. The room-air loop is closed, so its dew point is set by humidity control.
     Check how often the coldest Stage 1 plate surface or the seawater coil would fall below
     plausible room dew points.
  4. Exhaust recirculation between neighbouring modules (the multi-module question). CFD is
     needed to find the actual intake temperature rise; here we show how sensitive the design is
     to it, for rises of 1, 2 and 3 K at every hour.
  5. Seawater-first pump head: how much of the discharge-compliant seawater-first energy comes
     from the pipe-friction assumption.

All runs use the discharge-compliant seawater flow (bay_discharge.py) and the sized exchanger
(3 mm gap, 1.2 m plates) unless stated.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import hx_model as hx
import energy_model as em
import hx_sizing as hs
import bay_discharge as bd
from common import load

OUT = Path(__file__).parent / "results"
K_DEPOSIT = 0.5          # W/m-K, salt/dust deposit (assumed, typical of porous mineral layers)


def sized_assumptions(dp_out=None, dp_room=None):
    a = dict(em.A)
    d = hs.size_module(3e-3, 1.2)
    a["dp_stage1_room"] = d["dp_pa"] if dp_room is None else dp_room
    a["dp_stage1_out"] = d["dp_pa"] if dp_out is None else dp_out
    return a


def fouled_module(delta_m, s=3e-3, a=1.2):
    """Plate stack sized clean (s, a); outdoor channels lose 2*delta of gap to deposits.
    Returns new outdoor-side pressure drop and the module effectiveness at equal flows."""
    clean = hs.size_module(s, a)
    n_ch = clean["plates"] / 2
    area = clean["plates"] * a * a / 1.0 / 1.0           # one face of every plate wets each stream
    h_room = hs.NU * hs.K_AIR / (2 * s)
    s_f = s - 2 * delta_m
    h_out = hs.NU * hs.K_AIR / (2 * s_f)
    r_dep = delta_m / K_DEPOSIT
    ua = 1 / (1 / (h_room * area) + 1 / (h_out * area) + r_dep / area)
    ntu = ua / hs.C_MOD
    eps = hx.eps_crossflow_unmixed(ntu, 1.0)
    v = hs.Q_MOD / (n_ch * s_f * a)
    re = v * 2 * s_f * hs.RHO / hs.MU
    dp = (hs.FRE / re) * (a / (2 * s_f)) * hs.RHO * v**2 / 2 + hs.K_LOSS * hs.RHO * v**2 / 2
    return dp, eps


if __name__ == "__main__":
    df = load()
    lines = []
    p = lambda *x: (print(*x), lines.append(" ".join(str(y) for y in x)))

    # ---- 1. fan heat ---------------------------------------------------------------------
    p("1. FAN HEAT")
    implied_kw = hx.C_ROOM * hx.DT_RACK * 2 / 1e3
    for label, a in [("assumed 200 Pa exchanger", em.A), ("sized 67 Pa exchanger", sized_assumptions())]:
        fan_kw = em.room_fan_kw(a) * 2
        true_kw = 270 + fan_kw
        dT_true = true_kw * 1e3 / 2 / hx.C_ROOM
        p(f"  {label}: room fans {fan_kw:.1f} kW -> IT + fan heat {true_kw:.1f} kW "
          f"(rise {dT_true:.2f} K) vs {implied_kw:.1f} kW already removed in the model (rise {hx.DT_RACK:.2f} K)")

    # ---- 2. fouling ----------------------------------------------------------------------
    p("2. FOULING OF THE OUTDOOR SIDE (3 mm gap, 1.2 m plates, sized clean)")
    rows = []
    for delta_mm in (0.0, 0.1, 0.25, 0.5):
        dp_out, eps = fouled_module(delta_mm / 1e3)
        a = sized_assumptions(dp_out=dp_out)
        # effectiveness change: rerun with the fouled design effectiveness
        r = em.annual(em.hybrid(df, a=a, eps1_design=eps, coil_bypass=True))
        res, _, _ = hx.run(df, eps, 1.0)
        rows.append({"deposit_mm_per_wall": delta_mm, "outdoor_dp_pa": dp_out, "eps1": eps,
                     "air_only_%": 100 * (res.stage == "Air only").mean(),
                     "cooling_MWh_with_bypass": r["cooling_MWh"], "mech_PUE": r["mech_PUE"]})
    for s_mm in (4.0,):
        for delta_mm in (0.0, 0.25, 0.5):
            dp_out, eps = fouled_module(delta_mm / 1e3, s=s_mm / 1e3, a=1.5)
            clean = hs.size_module(s_mm / 1e3, 1.5)
            a = sized_assumptions(dp_out=dp_out, dp_room=clean["dp_pa"])
            r = em.annual(em.hybrid(df, a=a, eps1_design=eps, coil_bypass=True))
            res, _, _ = hx.run(df, eps, 1.0)
            rows.append({"deposit_mm_per_wall": delta_mm, "outdoor_dp_pa": dp_out, "eps1": eps,
                         "air_only_%": 100 * (res.stage == "Air only").mean(),
                         "cooling_MWh_with_bypass": r["cooling_MWh"], "mech_PUE": r["mech_PUE"],
                         "design": "4 mm gap, 1.5 m plates"})
    f = pd.DataFrame(rows).fillna({"design": "3 mm gap, 1.2 m plates"})
    f.round(3).to_csv(OUT / "robust_fouling.csv", index=False)
    p(f.round(3).to_string(index=False))

    # ---- 3. condensation -----------------------------------------------------------------
    p("3. CONDENSATION (hours per year; room-air dew point set by humidity control)")
    res, _, _ = hx.run(df, 0.75, 1.0)
    years = len(df) / 8760
    s1_on = res.after_stage1_c < hx.t_return(hx.SETPOINT) - 1e-6
    wall_min = (res.air_c + hx.SETPOINT) / 2            # coldest plate corner, equal h both sides
    s2_on = res.stage != "Air only"
    crows = []
    for dp in (9.0, 12.0, 13.0, 15.0):
        crows.append({"room_dew_point_c": dp,
                      "stage1_plate_hours_per_yr": ((wall_min < dp) & s1_on).sum() / years,
                      "seawater_coil_hours_per_yr": ((res.water_c < dp) & s2_on).sum() / years})
    c = pd.DataFrame(crows)
    c.round(1).to_csv(OUT / "robust_condensation.csv", index=False)
    p(c.round(1).to_string(index=False))
    p(f"  Bay water range {df.water_c.min():.1f}-{df.water_c.max():.1f} C; outside air min {df.air_c.min():.1f} C")

    # ---- 4. exhaust recirculation --------------------------------------------------------
    p("4. INTAKE TEMPERATURE RISE FROM NEIGHBOURING EXHAUST (sized exchanger + coil bypass, compliant flow)")
    a = sized_assumptions()
    rrows = []
    for rise in (0.0, 1.0, 2.0, 3.0):
        d2 = df.copy()
        d2["air_c"] = d2.air_c + rise
        e = bd.energy_compliant(d2, a, coil_bypass=True)
        res, _, _ = hx.run(d2, 0.75, 1.0)
        rrows.append({"intake_rise_K": rise, "air_only_%": 100 * (res.stage == "Air only").mean(),
                      "pump_runtime_%": e["pump_runtime_%"], "cooling_MWh": e["cooling_MWh"],
                      "mech_PUE": e["mech_PUE"], "seawater_1000m3": e["seawater_1000m3_per_yr"]})
    rr = pd.DataFrame(rrows)
    rr.round(3).to_csv(OUT / "robust_recirculation.csv", index=False)
    p(rr.round(2).to_string(index=False))

    # ---- 5. seawater-first pump head -----------------------------------------------------
    p("5. SEAWATER-FIRST (compliant) vs PIPE FRICTION AT DESIGN FLOW")
    srows = []
    orig = bd.STATIC_KPA
    for total in (100.0, 160.0, 220.0):
        def pk(m, md, eff=0.60, total=total):
            head = bd.STATIC_KPA + (total - bd.STATIC_KPA) * (m / md) ** 2
            return m / bd.RHO_SEA * head * 1e3 / eff / 1e3
        old = bd.pump_kw
        bd.pump_kw = pk
        s = bd.seawater_first_energy_compliant(df, em.A)
        h = bd.energy_compliant(df, a, coil_bypass=True)
        h2 = bd.energy_compliant(df, a, coil_bypass=False)
        bd.pump_kw = old
        srows.append({"design_head_kpa": total, "seawater_first_MWh": s["cooling_MWh"], "seawater_first_PUE": s["mech_PUE"],
                      "hybrid_sized_bypass_MWh": h["cooling_MWh"], "hybrid_sized_MWh": h2["cooling_MWh"]})
    sh = pd.DataFrame(srows)
    sh.round(2).to_csv(OUT / "robust_seawater_first_head.csv", index=False)
    p(sh.round(2).to_string(index=False))

    (OUT / "robustness_output.txt").write_text("\n".join(lines))

    # ---- 6. commercial-core effectiveness ------------------------------------------------
    p("6. STAGE 1 EFFECTIVENESS OF A TYPICAL COMMERCIAL CORE (dry mode ~0.60, Wei et al. 2024) vs 0.75 design")
    erows = []
    for eps in (0.60, 0.75, 0.80):
        res, _, _ = hx.run(df, eps, 1.0)
        for lbl, a in [("assumed 200 Pa", dict(em.A)), ("sized 67 Pa", sized_assumptions())]:
            e = bd.energy_compliant_eps(df, a, eps, coil_bypass=True)
            erows.append({"eps1_design": eps, "exchanger_dp": lbl, "air_only_%": 100 * (res.stage == "Air only").mean(),
                          "pump_runtime_%": e["pump_runtime_%"], "cooling_MWh_bypass": e["cooling_MWh"],
                          "mech_PUE": e["mech_PUE"], "seawater_1000m3": e["seawater_1000m3_per_yr"]})
    ee = pd.DataFrame(erows)
    ee.round(3).to_csv(OUT / "robust_effectiveness.csv", index=False)
    p(ee.round(2).to_string(index=False))
    (OUT / "robustness_output.txt").write_text("\n".join(lines))
