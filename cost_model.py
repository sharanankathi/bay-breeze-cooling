"""Screening-level cost comparison for one 270 kW module (two paths).

Energy comes from the discharge-compliant runs (results/bay_discharge_energy.csv, energy_comparison.csv).
Capital costs are LOW/HIGH ranges. Only the air-cooled chiller is from a published source (EIA 2023,
2022$, Total Installed Cost for air-cooled screw chillers, 820-1,250 $/ton; maintenance 20-50 $/ton-yr).
Stage 1 cores: Recutech quote (Oct 2026), epoxy 1.8x standard. Stage 2 coil: manufacturer budget quote (not itemised at the vendor's request) folded into the seawater-loop range. Every other capital figure is a placeholder to be replaced with vendor quotes; they are deliberately wide.
Chilled-water distribution for the chiller baseline is NOT counted, which favours the chiller.
Run: python cost_model.py
"""
from pathlib import Path
import pandas as pd

R = Path(__file__).parent / "results"
TON = 3.517  # kW thermal per ton

# --- energy (MWh/yr), discharge-compliant, vendor cores (84 Pa, 81.1 %) + coil bypass -------------------
# hybrid: Super Radiator 60x76-6R coil rating, pump limited to 290 GPM/path (v2_vendor_coil.py)
# seawater first: assumed eps 0.80 coil (favours that baseline; with the quoted coil it would need ~3,100 chiller h/yr)
E = {"hybrid": 182.9, "seawater_first": 200.8, "chiller_only": 741.1, "chiller_only_cop6": 544.0}
WATER = {"hybrid": 21_163, "seawater_first": 1_128_052}           # m3/yr
PRICE = {"paper basis": 0.125, "California industrial (EIA, Jul 2026)": 0.2511}

# --- capital, $ (LOW, HIGH) -------------------------------------------------------------------
PLATE_AREA = 6 * 1230                                             # m2, six sized cores
OA_CFM = 2 * 10.06 * 2118.88                                      # outdoor air, both paths
CAPEX = {
    "hybrid": {
        "Stage 1 cores: 12x Recutech REC+95-2000-31-EP (quote $2,880 ea; +25% shipping/handling high)": (12 * 2880, 12 * 2880 * 1.25),
        "Outdoor-air fans, filters, louvres, ducts (3-6 $/cfm)": (3 * OA_CFM, 6 * OA_CFM),
        "Seawater loop: coil, pump, strainer, intake/outfall (raised after a manufacturer budget quote for the coils)": (100_000, 200_000),
        "Trim chiller, ~14 ton (48 kW peak with the quoted coil; EIA 820-1,250 $/ton)": (14 * 820, 14 * 1250),
    },
    "seawater_first": {
        "Seawater loop, continuous duty (x1.3)": (130_000, 260_000),
        "Trim chiller, ~5 ton": (5_000, 10_000),
    },
    "chiller_only": {
        "Air-cooled chiller, 90-135 ton installed (EIA 820-1,250 $/ton)": (90 * 820, 135 * 1250),
    },
}
# --- maintenance, $/yr (LOW, HIGH) --------------------------------------------------------------
MAINT = {
    "hybrid": {"Seawater loop (floor model, Section 5)": (4_100, 4_100),
               "MERV 13 filter changes": (2_000, 6_000), "Plate-core cleaning": (1_000, 3_000)},
    "seawater_first": {"Seawater loop, continuous duty (Section 5)": (10_000, 10_000)},
    "chiller_only": {"Chiller (EIA 20-50 $/ton-yr)": (90 * 20, 135 * 50)},
}

tot = lambda d, i: sum(v[i] for v in d.values())
CRF = 0.08 * 1.08 ** 20 / (1.08 ** 20 - 1)                        # 8 %, 20 yr


def run():
    rows, out = [], []
    for case, items in CAPEX.items():
        for k, (lo, hi) in items.items():
            rows.append({"case": case, "item": k, "low_$": round(lo, -2), "high_$": round(hi, -2)})
    for case, items in MAINT.items():
        for k, (lo, hi) in items.items():
            rows.append({"case": case, "item": "O&M/yr: " + k, "low_$": lo, "high_$": hi})
    pd.DataFrame(rows).to_csv(R / "cost_items.csv", index=False)

    for pname, p in PRICE.items():
        for base, blab in (("chiller_only", "chiller only (COP 4)"), ("chiller_only_cop6", "chiller only (COP 6)")):
          save_e = (E[base] - E["hybrid"]) * 1e3 * p
          for lab, (ci, mi) in {"best": (0, 1), "worst": (1, 0)}.items():
            dcap = tot(CAPEX["hybrid"], ci) - tot(CAPEX["chiller_only"], 1 - ci)
            dom = tot(MAINT["chiller_only"], mi) - tot(MAINT["hybrid"], 1 - mi)
            net = save_e + dom
            out.append({"price": pname, "$/kWh": p, "vs": blab, "case": lab,
                        "extra_capex_$": dcap, "annual_saving_$": net,
                        "payback_yr": dcap / net if net > 0 else float("inf"),
                        "breakeven_capex_5yr_$": 5 * net, "breakeven_5yr_$per_kW_IT": 5 * net / 270})
        # vs seawater first: cost per m3 of Bay water not pumped
        save_e2 = (E["seawater_first"] - E["hybrid"]) * 1e3 * p
        for lab, (ci, mi) in {"best": (0, 1), "worst": (1, 0)}.items():
            dcap = tot(CAPEX["hybrid"], ci) - tot(CAPEX["seawater_first"], 1 - ci)
            dom = tot(MAINT["seawater_first"], mi) - tot(MAINT["hybrid"], 1 - mi)
            net_cost = dcap * CRF - save_e2 - dom                      # annualised extra cost
            out.append({"price": pname, "$/kWh": p, "vs": "seawater first", "case": lab,
                        "extra_capex_$": dcap, "annual_saving_$": save_e2 + dom,
                        "annualised_net_cost_$": net_cost,
                        "$per_m3_avoided": net_cost / (WATER["seawater_first"] - WATER["hybrid"])})
    t = pd.DataFrame(out)
    t.to_csv(R / "cost_comparison.csv", index=False)
    return t


if __name__ == "__main__":
    t = run()
    pd.set_option("display.width", 250)
    print("Capex totals ($): ", {k: (round(tot(v, 0), -3), round(tot(v, 1), -3)) for k, v in CAPEX.items()})
    print("O&M totals ($/yr):", {k: (tot(v, 0), tot(v, 1)) for k, v in MAINT.items()})
    print(t.round(3).to_string())
