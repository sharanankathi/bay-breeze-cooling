"""Figures for the energy model (run energy_model.py first)."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).parent / "results"
INK, MUTED, GRID, SURF = "#1f2328", "#5b636e", "#e6e7e9", "#fcfcfb"
# component colours: breeze fans blue, seawater pump orange, chiller green (as in fig 1), room fans yellow
COMP = [("room_fan_MWh", "Room-air fans", "#eda100"),
        ("outdoor_fan_MWh", "Outdoor-air fans", "#2a78d6"),
        ("pump_MWh", "Seawater pump", "#eb6834"),
        ("chiller_MWh", "Chiller", "#1baf7a")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})

t = pd.read_csv(R / "energy_comparison.csv", index_col=0)
order = ["Chiller only", "Seawater first", "Hybrid (breeze first)", "Hybrid + coil bypass"]
t = t.loc[order]

# ---- fig 4: annual cooling electricity by component ------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.6))
y = range(len(t))
left = [0.0] * len(t)
for col, lab, c in COMP:
    ax.barh(list(y), t[col], left=left, color=c, height=0.58, label=lab, edgecolor=SURF, linewidth=2)
    left = [l + v for l, v in zip(left, t[col])]
for i, (tot, pue) in enumerate(zip(t.cooling_MWh, t.mech_PUE)):
    ax.text(tot + 12, i, f"{tot:,.0f} MWh/yr   ·   mech. PUE {pue:.2f}", va="center", color=INK, fontsize=11)
ax.set_yticks(list(y), order)
ax.invert_yaxis()
ax.set_xlim(0, max(t.cooling_MWh) * 1.45)
ax.set_xlabel("Cooling electricity per year (MWh), 270 kW IT load")
ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.45, -0.18), frameon=False, labelcolor=INK)
ax.set_title("Annual cooling electricity: fans dominate once the chiller is gone", loc="left", color=INK, fontsize=13)
fig.tight_layout()
fig.savefig(R / "fig4_annual_cooling_energy.png", dpi=200)

# ---- fig 5: how much Bay water each option pumps ----------------------------------------
w = t.loc[["Seawater first", "Hybrid (breeze first)"]]
fig, ax = plt.subplots(figsize=(10, 2.8))
ax.barh([0, 1], w["seawater_1000m3_per_yr"], color="#eb6834", height=0.55, edgecolor=SURF, linewidth=2)
for i, (v, rt) in enumerate(zip(w["seawater_1000m3_per_yr"], w["pump_runtime_%"])):
    ax.text(v + 3, i, f"{v:,.0f} thousand m³/yr   ·   pump on {rt:.0f}% of hours", va="center", color=INK)
ax.set_yticks([0, 1], ["Seawater first", "Hybrid (breeze first)"])
ax.invert_yaxis(); ax.set_xlim(0, w["seawater_1000m3_per_yr"].max() * 2.0)
ax.set_xlabel("Bay water pumped through the coils per year (thousand m³)")
ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_title("Breeze first cuts Bay water use by ~85%", loc="left", color=INK, fontsize=13)
fig.tight_layout()
fig.savefig(R / "fig5_seawater_pumped.png", dpi=200)
print("saved fig4, fig5")

# ---- fig 6: Stage 1 plate heat exchanger sizing trade-off --------------------------------
s = pd.read_csv(R / "hx_sizing.csv")
fig, ax = plt.subplots(figsize=(10, 5.2))
cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
for c, g in zip(cols, (3, 4, 5, 6)):
    d = s[s.gap_mm == g]
    vol = d.path_volume_m3.iloc[0]
    ax.plot(d.plate_m, d.dp_pa, color=c, lw=2, marker="o", ms=8, markeredgecolor=SURF, markeredgewidth=2,
            label=f"{g} mm gap  ·  {vol:.0f} m³ per path")
    ax.text(d.plate_m.iloc[-1] + 0.03, d.dp_pa.iloc[-1], f"{g} mm", va="center", color=INK, fontsize=10)
ax.axhline(200, color=MUTED, lw=1.2, ls=(0, (4, 3)))
ax.text(1.0, 225, "200 Pa assumed in the energy model (compact commercial unit)", color=MUTED, fontsize=10)
pick = s[(s.gap_mm == 3) & (s.plate_m == 1.2)].iloc[0]
ax.annotate(f"Chosen: 3 mm, 1.2 m plates\n{pick.dp_pa:.0f} Pa, stack {pick.height_m:.1f} m tall",
            xy=(1.2, pick.dp_pa), xytext=(0.62, 75), color=INK, fontsize=10,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
ax.set_yscale("log"); ax.set_ylim(0.8, 400); ax.set_xlim(0.55, 1.62)
ax.set_xlabel("Plate size, flow length on each side (m)")
ax.set_ylabel("Pressure drop per side (Pa, log scale)")
ax.grid(color=GRID, which="major"); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, labelcolor=INK, fontsize=10)
ax.set_title("Stage 1 exchanger at ε = 0.75: wider gaps cut pressure drop but grow the box", loc="left", color=INK, fontsize=13)
fig.tight_layout()
fig.savefig(R / "fig6_hx_sizing_tradeoff.png", dpi=200)
print("saved fig6")
