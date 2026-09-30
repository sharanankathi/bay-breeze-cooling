"""Download hourly air and Bay water temperature data (public sources).

Air:   Open-Meteo historical archive (ERA5 reanalysis), SF Bay coastal point.
Water: NOAA CO-OPS station 9414290 (San Francisco), hourly water temperature.
"""
import json, time, urllib.request
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)
START, END = "2022-01-01", "2024-12-31"
LAT, LON = 37.79, -122.35


def fetch_air():
    url = ("https://archive-api.open-meteo.com/v1/archive"
           f"?latitude={LAT}&longitude={LON}&start_date={START}&end_date={END}"
           "&hourly=temperature_2m,relative_humidity_2m,dew_point_2m"
           "&timezone=America%2FLos_Angeles")
    with urllib.request.urlopen(url) as r:
        h = json.load(r)["hourly"]
    df = pd.DataFrame({"time": pd.to_datetime(h["time"]), "air_c": h["temperature_2m"],
                       "rh": h["relative_humidity_2m"], "dewpoint_c": h["dew_point_2m"]})
    df.to_csv(DATA / "air_hourly.csv", index=False)
    print(f"air: {len(df)} hours")


def fetch_water():
    rows = []
    for year in (2022, 2023, 2024):
        for q0, q1 in [("0101", "0401"), ("0401", "0701"), ("0701", "1001"), ("1001", "1231")]:
            url = ("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
                   f"?product=water_temperature&application=research&begin_date={year}{q0}"
                   f"&end_date={year}{q1}&station=9414290&time_zone=lst_ldt&units=metric"
                   "&interval=h&format=json")
            with urllib.request.urlopen(url) as r:
                rows += json.load(r).get("data", [])
            time.sleep(0.3)
    df = pd.DataFrame(rows)
    df = df[df["v"] != ""]
    df = pd.DataFrame({"time": pd.to_datetime(df["t"]), "water_c": df["v"].astype(float)})
    df = df.drop_duplicates("time")
    df.to_csv(DATA / "water_hourly.csv", index=False)
    print(f"water: {len(df)} hours")


if __name__ == "__main__":
    fetch_air()
    fetch_water()
