"""Step 5a: does the seawater return meet California's discharge-temperature rule?

California's Thermal Plan (State Water Resources Control Board) names San Francisco Bay as an
enclosed bay and states, for NEW discharges: "Thermal waste discharges having a maximum temperature
greater than 4 °F above the natural temperature of the receiving water are prohibited."
4 °F = 2.22 K. We design to a 2.0 K cap to leave margin for sensor error.

The earlier models used a fixed seawater flow (3.25 kg/s per path). This script:
  1. reports the discharge temperature rise that fixed flow actually produces;
  2. re-models the seawater coil with a variable-speed pump whose flow is set every hour so the
     water leaves no more than 2.0 K above Bay temperature (or less, if the coil needs more
     water to reach the air setpoint);
  3. applies the same rule to the seawater-first baseline;
  4. reports peak intake flow against the federal Clean Water Act 316(b) threshold for new
     facilities (design intake flow > 2 MGD, 40 CFR 125.81) and the screen area needed for the
     0.5 ft/s through-screen velocity limit (40 CFR 125.84).
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import hx_model as hx
import energy_model as em
from common import load

OUT = Path(__file__).parent / "results"
DT_CAP = 2.0                 # K, design cap on seawater temperature rise (rule: 2.22 K)
RULE_K = 4 * 5 / 9           # 2.22 K
RHO_SEA, CP_SEA = 1025.0, hx.CP_SEA
STATIC_KPA = 50.0            # lift to deck, ~5 m; the rest of the 160 kPa design head is friction
SCREEN_V = 0.5 * 0.3048      # m/s, 0.5 ft/s through-screen velocity
MGD = 3.785e3 / 86400        # m3/s per million US gallons per day
C_MAX = 8 * hx.C_ROOM        # W/K, upper bound on pump flow (~24 kg/s per path); beyond it the chiller trims

# Stage 2 coil conductance, fixed by the original design (eps 0.80 at 3.25 kg/s)
_cmin, _cmax = min(hx.C_ROOM, hx.C_SEA), max(hx.C_ROOM, hx.C_SEA)
NTU0 = brentq(lambda n: hx.eps_counterflow(n, _cmin / _cmax) - hx.EPS2_DESIGN, 1e-3, 50)
UA2 = NTU0 * _cmin


def coil_q(c_w, t_air_in, t_sea):
    """Heat (W) removed by the counterflow coil for water capacity rate c_w (W/K)."""
    cmin, cmax = min(hx.C_ROOM, c_w), max(hx.C_ROOM, c_w)
    eps = hx.eps_counterflow(UA2 / cmin, cmin / cmax)
    return eps * cmin * max(t_air_in - t_sea, 0.0)


def water_needed(t_air_in, t_sea, setpoint, c_max):
    """Smallest water capacity rate that reaches setpoint AND keeps the rise <= DT_CAP.
    Returns (c_w, heat_W, air_out). If c_max is not enough, runs at c_max and the chiller trims."""
    q_need = hx.C_ROOM * (t_air_in - setpoint)
    if q_need <= 0:
        return 0.0, 0.0, t_air_in
    def gap(c):
        return min(coil_q(c, t_air_in, t_sea), c * DT_CAP) - q_need
    if gap(c_max) < 0:                         # cannot fully meet setpoint within the cap
        c = c_max
        q = min(coil_q(c, t_air_in, t_sea), c * DT_CAP)
    else:
        c = brentq(gap, 1.0, c_max)
        q = q_need
    return c, q, t_air_in - q / hx.C_ROOM


def run_hybrid_capped(df, setpoint=hx.SETPOINT, c_max=None, eps1=0.75):
    res, e1, _ = hx.run(df, eps1, 1.0, setpoint)
    after1 = res.after_stage1_c.values
    t_sea = res.water_c.values
    if c_max is None:
        c_max = C_MAX
    out = np.zeros((len(res), 3))
    cache = {}
    for i, (a1, ts) in enumerate(zip(after1, t_sea)):
        if a1 <= setpoint + 1e-9:
            out[i] = (0.0, 0.0, a1)
            continue
        k = (round(a1, 2), round(ts, 2))
        if k not in cache:
            cache[k] = water_needed(a1, ts, setpoint, c_max)
        out[i] = cache[k]
    res["c_w"], res["q_sea_w"], res["after_stage2_c"] = out[:, 0], out[:, 1], out[:, 2]
    res["m_sea"] = res.c_w / CP_SEA
    res["dT_sea"] = np.where(res.c_w > 0, res.q_sea_w / res.c_w.replace(0, np.nan), 0.0)
    res["chiller_kw_per_path"] = np.maximum(res.after_stage2_c - setpoint, 0) * hx.C_ROOM / 1e3
    return res


def pump_kw(m, m_design, eff=0.60):
    head = STATIC_KPA + (160.0 - STATIC_KPA) * (m / m_design) ** 2      # pipes resized for m_design
    return m / RHO_SEA * head * 1e3 / eff / 1e3


def summarise(res, label, n_paths=2):
    years = len(res) / 8760
    on = res.m_sea > 0
    m_design = res.m_sea.max()
    pump = pump_kw(res.m_sea.values, m_design) * n_paths
    vol = (res.m_sea * 3600).sum() * n_paths / RHO_SEA / years
    peak_q = m_design * n_paths / RHO_SEA
    return {"case": label,
            "pump_runtime_%": 100 * on.mean(),
            "design_flow_kg_s_per_path": m_design,
            "design_intake_m3_s": peak_q,
            "design_intake_MGD": peak_q / MGD,
            "seawater_m3_per_yr": vol,
            "max_discharge_rise_K": res.dT_sea.max(),
            "hours_over_rule": int((res.dT_sea > RULE_K + 1e-6).sum()),
            "heat_to_bay_MWh_th": (res.q_sea_w.sum() * n_paths / 1e6) / years,
            "pump_MWh": pump.sum() / 1e3 / years,
            "chiller_hours_%": 100 * (res.chiller_kw_per_path > 1e-6).mean(),
            "screen_open_area_m2": peak_q / SCREEN_V}


def seawater_first_capped(df, setpoint=hx.SETPOINT):
    tr = hx.t_return(setpoint)
    out = [water_needed(tr, ts, setpoint, C_MAX) for ts in df.water_c.values]
    res = df[["time"]].copy()
    res["c_w"], res["q_sea_w"], res["after_stage2_c"] = zip(*out)
    res["m_sea"] = res.c_w / CP_SEA
    res["dT_sea"] = res.q_sea_w / res.c_w
    res["chiller_kw_per_path"] = np.maximum(res.after_stage2_c - setpoint, 0) * hx.C_ROOM / 1e3
    return res


if __name__ == "__main__":
    df = load()
    lines = []
    p = lambda *a: (print(*a), lines.append(" ".join(str(x) for x in a)))

    # 1. what the fixed-flow design does
    h = em.hybrid(df)
    s = em.seawater_first(df)
    for name, r, on in [("Hybrid, fixed 3.25 kg/s", h, h.pump_kw > 0), ("Seawater first, fixed 3.25 kg/s", s, np.ones(len(s), bool))]:
        dT = r.heat_to_bay_kw / 2 * 1e3 / hx.C_SEA
        p(f"{name}: max discharge rise {dT.max():.1f} K, mean {dT[on].mean():.2f} K, "
          f"{100 * (dT[on] > RULE_K).mean():.0f}% of pumping hours above the 2.22 K rule")

    # 2-3. compliant designs (variable-speed pump, rise capped at 2.0 K)
    rows = []
    for sp in (21.0, 24.0):
        rows.append(summarise(run_hybrid_capped(df, sp), f"Hybrid, {sp:.0f} C supply, rise <= 2 K"))
        rows.append(summarise(seawater_first_capped(df, sp), f"Seawater first, {sp:.0f} C supply, rise <= 2 K"))
    t = pd.DataFrame(rows)
    t.round(3).to_csv(OUT / "bay_discharge.csv", index=False)
    p(t.round(2).to_string(index=False))
    p(f"Rule: 4 F = {RULE_K:.2f} K. Design cap {DT_CAP} K. 316(b) new-facility threshold: 2 MGD = {2 * MGD:.4f} m3/s.")
    for scale in (1, 3.7, 37):
        q = t.loc[0, "design_intake_m3_s"] * scale
        p(f"  Hybrid at x{scale}: design intake {q:.3f} m3/s = {q / MGD:.2f} MGD")
    (OUT / "bay_discharge_output.txt").write_text("\n".join(lines))


def energy_compliant(df, a, coil_bypass=False, setpoint=hx.SETPOINT):
    """Annual cooling energy with the 2 K discharge cap (variable-speed seawater pump)."""
    r = em.hybrid(df, a=a, setpoint=setpoint, coil_bypass=coil_bypass)
    c = run_hybrid_capped(df, setpoint)
    m_d = c.m_sea.max()
    r["pump_kw"] = pump_kw(c.m_sea.values, m_d, a["pump_eff"]) * em.N_PATHS
    r["chiller_kw_e"] = c.chiller_kw_per_path.values * em.N_PATHS / a["chiller_cop_hybrid"]
    out = em.annual(r)
    out["seawater_1000m3_per_yr"] = summarise(c, "")["seawater_m3_per_yr"] / 1e3
    return out


def energy_compliant_eps(df, a, eps1, coil_bypass=False, setpoint=hx.SETPOINT):
    r = em.hybrid(df, a=a, eps1_design=eps1, setpoint=setpoint, coil_bypass=coil_bypass)
    c = run_hybrid_capped(df, setpoint, eps1=eps1)
    r["pump_kw"] = pump_kw(c.m_sea.values, c.m_sea.max(), a["pump_eff"]) * em.N_PATHS
    r["chiller_kw_e"] = c.chiller_kw_per_path.values * em.N_PATHS / a["chiller_cop_hybrid"]
    out = em.annual(r)
    out["seawater_1000m3_per_yr"] = summarise(c, "")["seawater_m3_per_yr"] / 1e3
    return out


def seawater_first_energy_compliant(df, a, setpoint=hx.SETPOINT):
    r = em.seawater_first(df, a, setpoint)
    c = seawater_first_capped(df, setpoint)
    r["pump_kw"] = pump_kw(c.m_sea.values, c.m_sea.max(), a["pump_eff"]) * em.N_PATHS
    r["chiller_kw_e"] = c.chiller_kw_per_path.values * em.N_PATHS / a["chiller_cop_hybrid"]
    out = em.annual(r)
    out["seawater_1000m3_per_yr"] = summarise(c, "")["seawater_m3_per_yr"] / 1e3
    return out


def energy_table(df):
    import hx_sizing as hs
    sized = dict(em.A)
    d = hs.size_module(3e-3, 1.2)
    sized["dp_stage1_room"] = sized["dp_stage1_out"] = d["dp_pa"]
    rows = []
    for label, fixed, comp in [
        ("Hybrid, assumed 200 Pa exchanger", lambda: em.annual(em.hybrid(df)), lambda: energy_compliant(df, em.A)),
        ("Hybrid, 200 Pa + coil bypass", lambda: em.annual(em.hybrid(df, coil_bypass=True)), lambda: energy_compliant(df, em.A, True)),
        ("Hybrid, sized 67 Pa exchanger", lambda: em.annual(em.hybrid(df, a=sized)), lambda: energy_compliant(df, sized)),
        ("Hybrid, sized 67 Pa + coil bypass", lambda: em.annual(em.hybrid(df, a=sized, coil_bypass=True)), lambda: energy_compliant(df, sized, True)),
        ("Seawater first", lambda: em.annual(em.seawater_first(df)), lambda: seawater_first_energy_compliant(df, em.A)),
    ]:
        f, c = fixed(), comp()
        rows.append({"case": label,
                     "fixed_flow_MWh": f["cooling_MWh"], "fixed_flow_PUE": f["mech_PUE"],
                     "fixed_flow_seawater_1000m3": f["seawater_1000m3_per_yr"],
                     "compliant_MWh": c["cooling_MWh"], "compliant_PUE": c["mech_PUE"],
                     "compliant_pump_MWh": c["pump_MWh"],
                     "compliant_seawater_1000m3": c["seawater_1000m3_per_yr"]})
    t = pd.DataFrame(rows)
    t.round(3).to_csv(OUT / "bay_discharge_energy.csv", index=False)
    return t


if __name__ == "__main__":
    t = energy_table(load())
    txt = t.round(2).to_string(index=False)
    print(txt)
    with open(OUT / "bay_discharge_output.txt", "a") as f:
        f.write("\n\nAnnual cooling energy, fixed 3.25 kg/s flow vs discharge-compliant variable flow\n" + txt)
