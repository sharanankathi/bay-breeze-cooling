"""Charts for the README / post. Run after hx_model.py."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from hx_model import T_RETURN, SETPOINT, stage1_eps

OUT = Path(__file__).parent / "results"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})

h = pd.read_csv(OUT / "hourly_baseline.csv", parse_dates=["time"])
t_star = T_RETURN - (T_RETURN - SETPOINT) / stage1_eps(0.75, 1.0)

# 1) Monthly share of hours by cooling stage (stacked bars, 2px surface gaps)
m = pd.read_csv(OUT / "monthly_stage_share.csv", index_col=0)
cols = [("Air only", BLUE), ("Air + seawater", ORANGE), ("Chiller trim", AQUA)]
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=200)
bottom = pd.Series(0.0, index=m.index)
for name, c in cols:
    v = m.get(name, pd.Series(0.0, index=m.index))
    ax.bar(m.index, v, bottom=bottom, color=c, width=0.7, edgecolor=SURF, linewidth=1.2, label=name)
    bottom += v
for x, v in zip(m.index, m["Air only"]):
    ax.text(x, v / 2, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
ax.set_ylabel("Share of hours (%)"); ax.set_ylim(0, 100); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_title("Which stage cools the servers, month by month (SF Bay, 2022–2024)", loc="left", color=INK, fontsize=12)
ax.legend(ncol=3, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.1))
fig.tight_layout(); fig.savefig(OUT / "fig1_monthly_stage_share.png"); plt.close(fig)

# 2) Daily outdoor air vs Bay water, 2023, with the air-only limit
d = h[h.time.dt.year == 2023].set_index("time").resample("D").agg({"air_c": "max", "water_c": "mean"})
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=200)
ax.plot(d.index, d.air_c, color=BLUE, lw=1.4)
ax.plot(d.index, d.water_c, color=ORANGE, lw=2)
ax.axhline(t_star, color=INK2, lw=1, ls="--")
ax.text(d.index[5], t_star + 0.5, f"Air-only limit ≈ {t_star:.1f} °C", color=INK2, fontsize=9)
ax.set_xlim(d.index[0] - pd.Timedelta(days=5), d.index[-1] + pd.Timedelta(days=75))
ax.text(d.index[-1] + pd.Timedelta(days=4), d.air_c.iloc[-10:].mean() + 1.2, "Outdoor air\n(daily max)", color=INK, fontsize=9, va="center")
ax.text(d.index[-1] + pd.Timedelta(days=4), d.water_c.iloc[-10:].mean() - 1.4, "Bay water\n(daily mean)", color=INK, fontsize=9, va="center")
ax.set_ylabel("Temperature (°C)"); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_title("Bay air and water through 2023: below the line, the breeze does it alone", loc="left", color=INK, fontsize=12)
fig.tight_layout(); fig.savefig(OUT / "fig2_air_vs_water_2023.png"); plt.close(fig)

# 3) Temperature chain on the warmest day with seawater assist
hm = h[h.water_measured]
day = hm.assign(date=hm.time.dt.date).groupby("date").air_c.max().idxmax()
x = h[h.time.dt.date == day]
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=200)
hrs = x.time.dt.hour
ax.axhline(T_RETURN, color=INK2, lw=1, ls=":")
ax.text(0.2, T_RETURN + 0.4, f"Hot-aisle return {T_RETURN:.2f} °C", color=INK2, fontsize=9)
series = [(x.air_c, BLUE, "-", "Outdoor air"), (x.water_c, ORANGE, "-", "Bay water"),
          (x.after_stage1_c, AQUA, "--", "After breeze HX"), (x.after_stage2_c, YELLOW, "-", "Supply to racks")]
for y, c, ls, lab in series:
    ax.plot(hrs, y, color=c, lw=2, ls=ls, marker="o", ms=3)
    ax.text(23.3, y.iloc[-1], lab, color=INK, fontsize=9, va="center")
ax.set_xlim(0, 27.5); ax.set_xticks(range(0, 24, 3)); ax.set_xlabel(f"Hour of day ({day})")
ax.set_ylabel("Temperature (°C)"); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_title("Hottest day with measured Bay water: breeze pre-cools, seawater finishes the job", loc="left", color=INK, fontsize=12)
fig.tight_layout(); fig.savefig(OUT / "fig3_hottest_day_chain.png"); plt.close(fig)
print("hottest day:", day)
