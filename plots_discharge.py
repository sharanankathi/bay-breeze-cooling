"""Figures for bay_discharge.py and robustness.py (run those first)."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).parent / "results"
INK, MUTED, GRID, SURF = "#1f2328", "#5b636e", "#e6e7e9", "#fcfcfb"
SEA, AIR = "#eb6834", "#2a78d6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})


def clean(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)


# ---- fig 7: compliant comparison -------------------------------------------------------
e = pd.read_csv(R / "bay_discharge_energy.csv").set_index("case")
rows = [("Seawater first", "Seawater first", SEA),
        ("Hybrid, sized 67 Pa exchanger", "Hybrid, sized exchanger", AIR),
        ("Hybrid, sized 67 Pa + coil bypass", "Hybrid, sized + coil bypass", AIR)]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"wspace": 0.55})
for i, (k, lab, c) in enumerate(rows):
    v = e.loc[k, "compliant_MWh"]; a1.barh(i, v, color=c, height=0.55)
    a1.text(v + 4, i, f"{v:.0f} MWh  ·  PUE {e.loc[k, 'compliant_PUE']:.2f}", va="center", color=INK, fontsize=10)
    w = e.loc[k, "compliant_seawater_1000m3"] * 1e3; a2.barh(i, w, color=c, height=0.55)
    a2.text(w * 1.25, i, f"{w:,.0f} m³", va="center", color=INK, fontsize=10)
for ax in (a1, a2):
    ax.set_yticks(range(len(rows)), [r[1] for r in rows]); ax.invert_yaxis(); clean(ax)
a1.set_xlim(0, 330); a1.set_xlabel("Cooling electricity per year (MWh)")
a2.set_xscale("log"); a2.set_xlim(1e4, 2e7); a2.set_xlabel("Bay water pumped per year (m³, log scale)")
a2.set_yticklabels([])
fig.suptitle("With the 2.2 K discharge rule applied to both designs: similar energy, about 40× less Bay water",
             x=0.02, ha="left", color=INK, fontsize=13)
fig.savefig(R / "fig7_discharge_compliant.png", dpi=200, bbox_inches="tight")

# ---- fig 8: intake recirculation sensitivity -------------------------------------------
r = pd.read_csv(R / "robust_recirculation.csv")
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(r.intake_rise_K, r["pump_runtime_%"], "o-", color=SEA, lw=2, label="Seawater pump runtime (% of hours)")
ax.set_ylabel("Pump runtime (% of hours)"); ax.set_xlabel("Intake air warmer than ambient (K), from neighbouring exhaust")
ax.set_xticks(r.intake_rise_K)
ax2 = ax.twinx()
ax2.plot(r.intake_rise_K, r.cooling_MWh, "s--", color=AIR, lw=2, label="Cooling electricity (MWh/yr)")
ax2.set_ylabel("Cooling electricity (MWh/yr)")
for a in (ax, ax2):
    for s in ("top",): a.spines[s].set_visible(False)
ax.grid(color=GRID); ax.set_axisbelow(True)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False, labelcolor=INK, fontsize=10)
ax.set_title("Each 1 K of exhaust recirculation adds about 7–11 points of pump runtime", loc="left", color=INK, fontsize=12)
fig.savefig(R / "fig8_recirculation_sensitivity.png", dpi=200, bbox_inches="tight")
print("ok")
