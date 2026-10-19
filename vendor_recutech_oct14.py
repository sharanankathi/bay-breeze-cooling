"""Re-run Paper 1 energy with Recutech's quoted REC+95 cores (Oct 14, 2026 email + datasheets).
Datasheet at 12,060 m3/h per unit (= one Stage 1 core, 6 per module): dry efficiency 76.6-76.7 %,
standard pressure drop 245 Pa (REC+95-2000-31) / 275 Pa (REC+95-1000-31-CXS); max pressure difference 1000 Pa.
Selector (recutech.selector.promaster.se, run Oct 14, 2026, epoxy option -EP, std. pressure drop):
2000 mm pack: 12,060 m3/h 245 Pa 76.6 %; 8,040 130 Pa 79.1 %; 6,030 84 Pa 81.1 %; 4,020 48 Pa 84.2 %.
Run: python vendor_recutech_oct14.py"""
import pandas as pd
from common import load
import energy_model as em, bay_discharge as bd
df = load()
rows = []
for label, dp, eps in [("Sized plain plate (paper)", 67, 0.75), ("REC+95-2000-31 (245 Pa)", 245, 0.766),
                       ("REC+95-1000-31-CXS (275 Pa)", 275, 0.766),
                       ("2x REC+95-2000-31 parallel, 6,030 m3/h each (selector)", 84, 0.811),
                       ("3x REC+95-2000-31 parallel, 4,020 m3/h each (selector)", 48, 0.842)]:
    a = dict(em.A); a["dp_stage1_room"] = a["dp_stage1_out"] = dp
    o = bd.energy_compliant_eps(df, a, eps, coil_bypass=True)
    rows.append({"core": label, "dp_Pa": dp, "eps": eps, "cooling_MWh": o["cooling_MWh"], "mech_PUE": o["mech_PUE"],
                 "pump_runtime_pct": o["pump_runtime_%"], "seawater_1000m3": o["seawater_1000m3_per_yr"]})
t = pd.DataFrame(rows); t.to_csv("results/vendor_recutech_oct14.csv", index=False); print(t.round(3).to_string())
