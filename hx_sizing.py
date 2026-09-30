"""Step 4: how big is the Stage 1 air-to-air exchanger, and what is its real pressure drop?

Geometry: cross-flow plate heat exchanger (the common type for indirect air-side economisers).
A stack of thin aluminium plates, square (a x a), with alternating channels: room air flows one way,
outdoor air at 90 degrees, both across the full plate length a. Each path is split into 3 identical
modules (as in the CAD), each carrying 1/3 of the room and outdoor air.

For every combination of channel gap s and plate size a, the stack height H is found so that the
module reaches the design effectiveness (0.75 at equal airflows, the value used in hx_model.py).
Then the pressure drop on each side follows directly.

Physics (parallel-plate channels, flow is laminar for these gaps and velocities):
  hydraulic diameter  Dh = 2 s
  heat transfer       Nu = 7.54 (fully developed, constant wall temperature; conservative)
                      h  = Nu k / Dh   -> independent of velocity in laminar flow
  friction            f Re = 96 (Darcy),  dp_core = f (a/Dh) rho V^2 / 2
  entry + exit loss   K = 1.0 x rho V^2 / 2 (channel velocity)
  overall             1/UA = 1/(h A) + 1/(h A)   (same h both sides, wall resistance negligible)
"""
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import hx_model as hx

OUT = Path(__file__).parent / "results"

RHO, MU, K_AIR, CP = 1.18, 1.85e-5, 0.026, 1006.0
NU, FRE, K_LOSS = 7.54, 96.0, 1.0
T_PLATE = 0.15e-3            # m, aluminium plate thickness
N_MODULES = 3                # per path
Q_MOD = hx.V_ROOM / N_MODULES          # m3/s room air per module (outdoor air equal at ratio 1.0)
C_MOD = Q_MOD * RHO * CP
EPS_DESIGN = 0.75
NTU_REQ = brentq(lambda n: hx.eps_crossflow_unmixed(n, 1.0) - EPS_DESIGN, 1e-3, 50)
UA_REQ = NTU_REQ * C_MOD


def size_module(s, a):
    """Stack height H [m] and side pressure drop [Pa] for gap s [m] and plate size a [m]."""
    dh = 2 * s
    h = NU * K_AIR / dh
    area_req = 2 * UA_REQ / h                  # 1/UA = 2/(hA)  ->  A = 2 UA / h
    n_plates = math.ceil(area_req / a**2)
    n_ch = n_plates / 2                        # channels per stream (alternating)
    height = n_plates * (s + T_PLATE)
    v = Q_MOD / (n_ch * s * a)                 # channel velocity
    re = v * dh * RHO / MU
    f = FRE / re
    dp = f * (a / dh) * RHO * v**2 / 2 + K_LOSS * RHO * v**2 / 2
    face_v = Q_MOD / (a * height / 2)          # velocity approaching one stream's face
    return dict(gap_mm=s * 1e3, plate_m=a, plates=n_plates, height_m=height,
                module_volume_m3=a * a * height, path_volume_m3=N_MODULES * a * a * height,
                area_m2_per_module=n_plates * a**2, channel_v_ms=v, face_v_ms=face_v, Re=re, dp_pa=dp)


if __name__ == "__main__":
    print(f"Design: eps {EPS_DESIGN} at equal flows -> NTU {NTU_REQ:.2f}, UA {UA_REQ/1e3:.1f} kW/K per module "
          f"({N_MODULES} modules per path, {Q_MOD:.2f} m3/s each)")
    rows = [size_module(s / 1e3, a) for s in (3, 4, 5, 6, 8) for a in (0.6, 0.8, 1.0, 1.2, 1.5)]
    t = pd.DataFrame(rows)
    t.round(3).to_csv(OUT / "hx_sizing.csv", index=False)
    print(t[["gap_mm", "plate_m", "plates", "height_m", "path_volume_m3", "channel_v_ms", "Re", "dp_pa"]]
          .round(2).to_string(index=False))

    # ---- feed the calculated pressure drops back into the energy model -----------------------
    import energy_model as em
    from common import load
    df = load()
    picks = [("Assumed in energy model (compact commercial unit)", None),
             ("Plain plates, 3 mm gap, 1.2 m plates", (3, 1.2)),
             ("Plain plates, 3 mm gap, 1.5 m plates", (3, 1.5)),
             ("Plain plates, 4 mm gap, 1.5 m plates", (4, 1.5))]
    er = []
    for label, geo in picks:
        a = dict(em.A)
        if geo:
            d = size_module(geo[0] / 1e3, geo[1])
            a["dp_stage1_room"] = a["dp_stage1_out"] = d["dp_pa"]
            vol, height = d["path_volume_m3"] * 2, d["height_m"]
        else:
            vol, height = float("nan"), float("nan")
        r = em.annual(em.hybrid(df, a=a))
        er.append({"design": label, "stage1_dp_pa": a["dp_stage1_room"], "stack_height_m": height,
                   "total_volume_m3_both_paths": vol, "cooling_MWh": r["cooling_MWh"], "mech_PUE": r["mech_PUE"]})
        r2 = em.annual(em.hybrid(df, a=a, coil_bypass=True))
        er[-1]["cooling_MWh_with_bypass"] = r2["cooling_MWh"]
        er[-1]["mech_PUE_with_bypass"] = r2["mech_PUE"]
    er = pd.DataFrame(er)
    er.round(3).to_csv(OUT / "hx_sizing_energy.csv", index=False)
    print(er.round(3).to_string(index=False))
