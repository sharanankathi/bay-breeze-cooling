"""Preprint v2: Super Radiator Coils quote A108576-1 (Oct 19 2026) for the Stage 2 seawater coil.
Model 60x76-6R-0.625/96, Cu-Ni 90/10 tubes/headers, 316 SS casing, Al fins with E-Coat Zx; 21,300 ACFM,
92 F entering air, 59 F seawater. Rated: 290 GPM -> 513,132 Btu/h, 0.47 in.H2O, 10.77 ft tube dP;
150 GPM -> 476,094; 50 GPM -> 335,974.  (pricing and lead time withheld at the vendor's request).
Fits the coil's conductance UA(c_w) from the three ratings (counterflow eps-NTU, 1/UA = Ra + Rw c_w^-0.8)
and re-runs the v2 vendor case with it.  Run: python v2_vendor_coil.py"""
import numpy as np, pandas as pd
from scipy.optimize import brentq, least_squares
import hx_model as hx, energy_model as em, bay_discharge as bd
from common import load

F2C = lambda f: (f - 32) / 1.8
GPM2KG = 3.785e-3 / 60 * 1025
T_A, T_W = F2C(92), F2C(59)
pts = [(290, 513_132), (150, 476_094), (50, 335_974)]
C_AIR = 513_132 * 0.29307 / (T_A - F2C(68.8))           # W/K from the rated air-side drop
rows, ua = [], []
for g, btu in pts:
    q = btu * 0.29307; cw = g * GPM2KG * 3990
    cmin, cmax = min(C_AIR, cw), max(C_AIR, cw); eps = q / (cmin * (T_A - T_W))
    ntu = brentq(lambda n: hx.eps_counterflow(n, cmin / cmax) - eps, 1e-4, 50)
    ua.append(ntu * cmin); rows.append({"GPM": g, "kg_s": g * GPM2KG, "kW": q / 1e3, "eps": eps, "UA_kW_K": ntu * cmin / 1e3,
                                        "rise_K": q / cw})
cw_pts = np.array([g * GPM2KG * 3990 for g, _ in pts]); ua = np.array(ua)
fit = least_squares(lambda p: (1 / (p[0] + p[1] * cw_pts ** -0.8) - ua) / ua, [1e-5, 1e-2], bounds=([0, 0], [1, 10]))
RA, RW = fit.x
UA = lambda cw: 1 / (RA + RW * max(cw, 1.0) ** -0.8)
fitdf = pd.DataFrame(rows); fitdf["UA_fit_kW_K"] = [UA(c) / 1e3 for c in cw_pts]
print(fitdf.round(3).to_string()); print("model UA2 (eps 0.80 @3.25 kg/s): %.1f kW/K" % (bd.UA2 / 1e3))

def coil_q_vendor(c_w, t_air_in, t_sea):
    cmin, cmax = min(hx.C_ROOM, c_w), max(hx.C_ROOM, c_w)
    eps = hx.eps_counterflow(UA(c_w) / cmin, cmin / cmax)
    return eps * cmin * max(t_air_in - t_sea, 0.0)

df = load(); out = []
C_RATED = 290 * GPM2KG * 3990            # W/K, coil rated flow (290 GPM) used as the pump flow limit
for label, fn, cmax in (("model coil (eps 0.80)", bd.coil_q, bd.C_MAX), ("Super Radiator 60x76-6R", coil_q_vendor, C_RATED)):
    bd.coil_q = fn; bd.C_MAX = cmax
    for cap in (2.0, 1.5):
        bd.DT_CAP = cap
        a = dict(em.A); a["dp_stage1_room"] = a["dp_stage1_out"] = 84
        o = bd.energy_compliant_eps(df, a, 0.811, coil_bypass=True)
        c = bd.run_hybrid_capped(df, eps1=0.811); s_ = bd.summarise(c, "")
        o2 = bd.seawater_first_energy_compliant(df, dict(em.A))
        c2 = bd.seawater_first_capped(df); s2 = bd.summarise(c2, "")
        for case, oo, cc, ss in (("hybrid", o, c, s_), ("seawater first", o2, c2, s2)):
            out.append({"coil": label, "cap_K": cap, "case": case, "MWh": oo["cooling_MWh"], "PUE": oo["mech_PUE"],
                        "pump_runtime_pct": ss["pump_runtime_%"], "sea_m3": ss["seawater_m3_per_yr"],
                        "design_GPM_path": ss["design_flow_kg_s_per_path"] / GPM2KG, "design_MGD": ss["design_intake_MGD"],
                        "chiller_h_yr": ss["chiller_hours_%"] * 87.6, "peak_chiller_kW_path": cc.chiller_kw_per_path.max(),
                        "max_rise_K": ss["max_discharge_rise_K"], "heat_to_bay_MWh": ss["heat_to_bay_MWh_th"]})
t = pd.DataFrame(out); t.to_csv("results/v2_vendor_coil.csv", index=False); fitdf.to_csv("results/v2_vendor_coil_fit.csv", index=False)
pd.set_option("display.width", 250); print(t.round(3).to_string())
