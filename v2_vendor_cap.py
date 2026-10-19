"""Preprint v2: vendor-backed Stage 1 (12x Recutech REC+95-2000-31-EP, two per core position,
6,030 m3/h each: 84 Pa, 81.1 % dry, from the online selector, Oct 14 2026) and a 1.5 K discharge-cap
sensitivity.  Run: python v2_vendor_cap.py"""
import pandas as pd
from common import load
import energy_model as em, bay_discharge as bd
df = load()
rows = []
for cap in (2.0, 1.5):
    bd.DT_CAP = cap
    for label, dp, eps in [("Hybrid, sized flat plates", 67, 0.75), ("Hybrid, 12x REC+95-2000-31-EP", 84, 0.811)]:
        a = dict(em.A); a["dp_stage1_room"] = a["dp_stage1_out"] = dp
        o = bd.energy_compliant_eps(df, a, eps, coil_bypass=True)
        c = bd.run_hybrid_capped(df, eps1=eps); s = bd.summarise(c, "")
        rows.append({"cap_K": cap, "case": label, "MWh": o["cooling_MWh"], "PUE": o["mech_PUE"],
                     "pump_runtime_pct": s["pump_runtime_%"], "sea_m3": s["seawater_m3_per_yr"],
                     "design_MGD": s["design_intake_MGD"], "chiller_h_pct": s["chiller_hours_%"]})
    a = dict(em.A)
    o = bd.seawater_first_energy_compliant(df, a)
    c = bd.seawater_first_capped(df); s = bd.summarise(c, "")
    rows.append({"cap_K": cap, "case": "Seawater first", "MWh": o["cooling_MWh"], "PUE": o["mech_PUE"],
                 "pump_runtime_pct": s["pump_runtime_%"], "sea_m3": s["seawater_m3_per_yr"],
                 "design_MGD": s["design_intake_MGD"], "chiller_h_pct": s["chiller_hours_%"]})
t = pd.DataFrame(rows); t.to_csv("results/v2_vendor_cap.csv", index=False)
pd.set_option("display.width", 200); print(t.round(3).to_string())
