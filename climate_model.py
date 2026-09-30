"""Step 1: how often is outside air or Bay water cold enough? (simple approach-temperature screen)

Direct free-air cooling is checked against ASHRAE Class A2 envelopes (temperature AND humidity).
Indirect economizer cooling only needs the air/water to be colder than supply - approach.
"""
from pathlib import Path
import pandas as pd
from common import load

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)

df = load()
direct_rec = df.air_c.between(18, 27) & df.dewpoint_c.between(5.5, 15) & (df.rh <= 60)
direct_a2 = df.air_c.between(10, 35) & df.dewpoint_c.between(-12, 21) & df.rh.between(8, 80)

rows = []
for supply in (18, 21):
    for approach in (3, 5):
        t = supply - approach
        air = df.air_c <= t
        water = ~air & (df.water_c <= t)
        rows.append({"supply_c": supply, "approach_c": approach, "air_only_%": 100 * air.mean(),
                     "seawater_%": 100 * water.mean(), "neither_%": 100 * (~air & ~water).mean()})
screen = pd.DataFrame(rows).round(1)

print(f"Hours analysed: {len(df)} | mean air {df.air_c.mean():.1f} C, mean RH {df.rh.mean():.1f}%")
print(f"Direct free air, ASHRAE recommended: {100*direct_rec.mean():.1f}% of hours")
print(f"Direct free air, ASHRAE allowable A2: {100*direct_a2.mean():.1f}% of hours")
print(screen.to_string(index=False))
screen.to_csv(OUT / "climate_screen.csv", index=False)
