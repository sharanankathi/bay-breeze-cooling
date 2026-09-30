"""Shared data loading. Water gaps are filled with month-of-year climatology from measured data."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"


def load(fill_water=True):
    air = pd.read_csv(DATA / "air_hourly.csv", parse_dates=["time"])
    water = pd.read_csv(DATA / "water_hourly.csv", parse_dates=["time"])
    df = air.merge(water, on="time", how="left")
    df["water_measured"] = df["water_c"].notna()
    if fill_water:
        clim = water.assign(m=water.time.dt.month, h=water.time.dt.hour).groupby(["m", "h"]).water_c.mean()
        key = list(zip(df.time.dt.month, df.time.dt.hour))
        df.loc[~df.water_measured, "water_c"] = [clim.get(k) for k, m in zip(key, df.water_measured) if not m]
    return df
