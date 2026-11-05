"""Audit the archived VISSIM CSV exports (results.zip) and write derived tables.

The raw exports are NOT distributed in this repository (see data/raw/README.md).
Point --raw at the extracted ``results`` folder that contains Base/, Encroach/,
Lane_Block/, Monsoon/ and Night/.

    python analysis/audit_exports.py --raw data/raw/results

Outputs (data/derived/):
    raw_manifest.csv            file checksums, row counts, run and interval counts
    run_identity.csv            content hash of every SIMRUN (SIMRUN column excluded)
    distinct_simulations.csv    one row per *distinct* simulation output + metrics
    comparisons.csv             fixed vs adaptive % change for candidate run pairs
    interval_network_delay.csv  per-interval DELAYAVG(ALL) for each distinct simulation

Every metric is a descriptive summary of ONE simulation (one random seed).
No statistical inference is possible from these data; see docs/evidence_audit.md.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

SCENARIOS = ["Base", "Encroach", "Lane_Block", "Monsoon", "Night"]
CONTROLLERS = ["fixed", "adaptive"]
EXPORTS = {
    "vehicle_network": "Vehicle Network Performance",
    "node": "Node Results",
    "data_collection": "Data Collection",
}
OUT = Path(__file__).resolve().parents[1] / "data" / "derived"

# Run pairs examined. "report_figure_pair" = the runs whose 60-interval network-delay
# series match the time-series figures printed in BOTH the UG report (Nov 2025) and
# the thesis (Apr 2026); see docs/evidence_audit.md section 3.
# Encroach fixed runs 2 and 13-21 are identical; run 2 is the earliest.
PAIRS = [
    ("Base", 3, 8, "report_figure_pair"),
    ("Base", 10, 19, "later_batch_pair"),
    ("Encroach", 2, 4, "report_figure_pair"),
    ("Encroach", 2, 22, "later_batch_pair"),
    ("Lane_Block", 11, 22, "later_batch_pair"),
    ("Monsoon", 10, 21, "later_batch_pair"),
    ("Night", 1, 11, "later_batch_pair"),
]


def find_csv(raw: Path, scenario: str, controller: str, export: str) -> Path:
    hits = sorted((raw / scenario).glob(f"{controller}_*/*{EXPORTS[export]}*.csv"))
    if len(hits) != 1:
        raise FileNotFoundError(f"{scenario}/{controller}/{export}: found {hits}")
    return hits[0]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_hash(group: pd.DataFrame) -> str:
    g = group.drop(columns="SIMRUN")
    g = g.sort_values(list(g.columns[:2])).round(6)
    return hashlib.md5(g.to_csv(index=False).encode()).hexdigest()[:12]


def interval_no(series: pd.Series) -> pd.Series:
    return series.astype(str).str.split("-").str[-1].astype(int)


def metrics(vn: pd.DataFrame, node: pd.DataFrame) -> dict:
    tot = node[node["MOVEMENT"] == "1"]
    mov = node[node["MOVEMENT"] != "1"]
    vehs = tot["VEHS(ALL)"].sum()
    d = vn.sort_values("interval")["DELAYAVG(ALL)"].to_numpy()
    return {
        "n_intervals": len(vn),
        "net_delay_mean_s_per_veh": vn["DELAYAVG(ALL)"].mean(),
        "net_stops_mean_per_veh": vn["STOPSAVG(ALL)"].mean(),
        "net_speed_mean_as_exported": vn["SPEEDAVG(ALL)"].mean(),
        "net_vehicles_arrived": int(vn["VEHARR(ALL)"].sum()),
        # Vehicles that could not enter the network (stock at end of the last interval)
        # and their accumulated waiting time, as exported by VISSIM.
        "net_latent_demand_end_veh": int(vn.sort_values("interval")["DEMANDLATENT"].iloc[-1]),
        "net_latent_delay_end_h": vn.sort_values("interval")["DELAYLATENT"].iloc[-1] / 3600,
        "node_vehicles": int(vehs),
        "node_delay_vehweighted_s_per_veh": float(
            np.average(tot["VEHDELAY(ALL)"].fillna(0), weights=tot["VEHS(ALL)"])
        ),
        "node_delay_movement_mean_s": mov["VEHDELAY(ALL)"].mean(),
        "node_stops_vehweighted": float(
            np.average(tot["STOPS(ALL)"].fillna(0), weights=tot["VEHS(ALL)"])
        ),
        "node_qlen_mean_m": tot["QLEN"].mean(),
        "node_co_per_veh_as_exported": tot["EMISSIONSCO"].sum() / vehs,
        "node_nox_per_veh_as_exported": tot["EMISSIONSNOX"].sum() / vehs,
        "node_voc_per_veh_as_exported": tot["EMISSIONSVOC"].sum() / vehs,
        "node_fuel_per_veh_as_exported": tot["FUELCONSUMPTION"].sum() / vehs,
        "first_interval_net_delay": d[0],
        "peak_interval_net_delay": d.max(),
        "peak_interval_no": int(np.argmax(d)) + 1,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True)
    args = ap.parse_args()
    raw = args.raw
    OUT.mkdir(parents=True, exist_ok=True)

    manifest, identity, data = [], [], {}
    for sc in SCENARIOS:
        for ctl in CONTROLLERS:
            for ex in EXPORTS:
                p = find_csv(raw, sc, ctl, ex)
                df = pd.read_csv(p, low_memory=False).copy()
                df = df.assign(interval=interval_no(df["TIMEINT"]))
                if "MOVEMENT" in df:
                    df["MOVEMENT"] = df["MOVEMENT"].astype(str)
                data[(sc, ctl, ex)] = df
                manifest.append({
                    "scenario": sc, "controller": ctl, "export": ex,
                    "file": str(p.relative_to(raw)), "bytes": p.stat().st_size,
                    "sha256": sha256(p), "rows": len(df),
                    "n_simrun": df["SIMRUN"].nunique(), "n_intervals": df["interval"].nunique(),
                    "simruns": " ".join(map(str, sorted(df["SIMRUN"].unique()))),
                })
                for run, g in df.drop(columns="interval").groupby("SIMRUN"):
                    identity.append({"scenario": sc, "controller": ctl, "export": ex,
                                     "simrun": int(run), "content_hash": run_hash(g)})
        for inpx in sorted((raw / sc).glob("*.inpx")):
            manifest.append({"scenario": sc, "controller": "", "export": "inpx",
                             "file": str(inpx.relative_to(raw)), "bytes": inpx.stat().st_size,
                             "sha256": sha256(inpx)})
    for py in sorted(raw.glob("*.py")):
        manifest.append({"scenario": "", "controller": "", "export": "python",
                         "file": py.name, "bytes": py.stat().st_size, "sha256": sha256(py)})
    pd.DataFrame(manifest).to_csv(OUT / "raw_manifest.csv", index=False)

    ident = pd.DataFrame(identity)
    # Label distinct outputs per scenario/export so identical runs share a label
    # across controllers (e.g. Base fixed runs 10-18 == Base adaptive runs 19-27).
    labels = {}
    for (sc, ex), g in ident.groupby(["scenario", "export"]):
        for i, h in enumerate(dict.fromkeys(g.sort_values(["controller", "simrun"], ascending=[False, True])["content_hash"])):
            labels[(sc, ex, h)] = f"{sc}-S{i + 1}"
    ident["distinct_output"] = [labels[(r.scenario, r.export, r.content_hash)] for r in ident.itertuples()]
    ident.to_csv(OUT / "run_identity.csv", index=False)

    # One row per distinct Vehicle-Network output per controller folder.
    rows, series = [], []
    vn_ident = ident[ident.export == "vehicle_network"]
    for (sc, ctl, lab), g in vn_ident.groupby(["scenario", "controller", "distinct_output"]):
        runs = sorted(g.simrun)
        rep = runs[0]
        vn = data[(sc, ctl, "vehicle_network")]
        nd = data[(sc, ctl, "node")]
        m = metrics(vn[vn.SIMRUN == rep], nd[nd.SIMRUN == rep])
        rows.append({"scenario": sc, "controller": ctl, "distinct_output": lab,
                     "representative_simrun": rep, "n_identical_runs": len(runs),
                     "member_simruns": " ".join(map(str, runs)), **m})
        s = vn[vn.SIMRUN == rep].sort_values("interval")
        for iv, dly in zip(s["interval"], s["DELAYAVG(ALL)"]):
            series.append({"scenario": sc, "controller": ctl, "simrun": rep,
                           "interval": int(iv), "start_s": 600 + 60 * (int(iv) - 1),
                           "delay_avg_s_per_veh": dly})
    distinct = pd.DataFrame(rows)
    distinct.to_csv(OUT / "distinct_simulations.csv", index=False)
    pd.DataFrame(series).to_csv(OUT / "interval_network_delay.csv", index=False)

    # Fixed vs adaptive comparisons for the examined pairs.
    keys = [c for c in distinct.columns if c.startswith(("net_", "node_"))]
    comp = []
    for sc, rf, ra, kind in PAIRS:
        f = distinct[(distinct.scenario == sc) & (distinct.controller == "fixed")
                     & distinct.member_simruns.str.split().apply(lambda x: str(rf) in x)]
        a = distinct[(distinct.scenario == sc) & (distinct.controller == "adaptive")
                     & distinct.member_simruns.str.split().apply(lambda x: str(ra) in x)]
        if len(f) != 1 or len(a) != 1:
            raise RuntimeError(f"Pair {sc} {rf}/{ra} not found")
        f, a = f.iloc[0], a.iloc[0]
        identical = f.distinct_output == a.distinct_output
        for k in keys:
            comp.append({"scenario": sc, "pair_type": kind, "fixed_simrun": rf, "adaptive_simrun": ra,
                         "outputs_identical": identical, "metric": k,
                         "fixed": f[k], "adaptive": a[k],
                         "pct_change_adaptive_vs_fixed": 100 * (a[k] - f[k]) / f[k] if f[k] else np.nan})
    pd.DataFrame(comp).to_csv(OUT / "comparisons.csv", index=False)
    print(f"Wrote derived tables to {OUT}")


if __name__ == "__main__":
    main()
