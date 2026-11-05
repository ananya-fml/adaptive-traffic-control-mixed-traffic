"""Build and run the recovered SUMO packages; record summary statistics.

Requires SUMO >= 1.20 (tested with 1.28.0 from PyPI: ``pip install eclipse-sumo``).

    python sumo/run_scenarios.py            # all runs, writes data/derived/sumo_runs.csv
    python sumo/run_scenarios.py --quick    # Phase 5C base only (CI smoke test)

The archived input files are never modified. Networks are rebuilt with netconvert
into a temporary directory; command-line options listed in ``RUNS`` document
every override (e.g. the Phase 5C default .sumocfg contains
``ignore-junction-blocker="true"``, which SUMO rejects, so that run is reproduced
with the value 5 used in the later base/encroachment configs).

These are runs of an exploratory, uncalibrated SUMO model with one random seed.
They demonstrate executability and operating regime (stable vs gridlocked),
not equivalence with the VISSIM model and not controller performance.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "derived" / "sumo_runs.csv"

NETS = {
    "ug_phase5_fixed3": ("lanka_phase5_fixed3", None),  # also ships a compiled .net.xml
    "phase5c": ("lanka_phase5c", None),
}

# (run id, package, route file, extra sumo args, note)
RUNS = [
    ("ug_fixed3_full", "ug_phase5_fixed3", "lanka_phase5_fixed3.sumocfg", [],
     "As delivered for the UG report; full VISSIM demand; compiled net as archived"),
    ("p5c_default_cfg", "phase5c", "lanka_phase5c.sumocfg", [],
     "Archived default config, unmodified (expected to fail: invalid option value)"),
    ("p5c_full", "phase5c", "lanka_phase5c.sumocfg",
     ["-r", "lanka_phase5c_full.rou.xml", "--ignore-junction-blocker", "5"],
     "Full VISSIM-equivalent demand; ignore-junction-blocker overridden to 5"),
    ("p5c_reduced", "phase5c", "lanka_phase5c.sumocfg",
     ["-r", "lanka_phase5c_reduced.rou.xml", "--ignore-junction-blocker", "5"],
     "Reduced demand (~80%); ignore-junction-blocker overridden to 5"),
    ("p5c_base_stable", "phase5c", "lanka_base_stable.sumocfg", [],
     "Archived 'base' config, unmodified (~31% of VISSIM demand)"),
    ("p5c_encroachment", "phase5c", "lanka_encroachment.sumocfg", [],
     "Archived 'encroachment' config, unmodified (same reduced demand + kerbside stops)"),
]


def sumo_bin(name: str) -> str:
    home = os.environ.get("SUMO_HOME")
    if not home:
        try:
            import sumo  # type: ignore
            home = sumo.SUMO_HOME
        except ImportError:
            pass
    cand = Path(home, "bin", name) if home else None
    if cand and cand.exists():
        return str(cand)
    found = shutil.which(name)
    if not found:
        sys.exit(f"{name} not found: install SUMO (pip install eclipse-sumo) or set SUMO_HOME")
    return found


def total_demand(route_file: Path) -> float:
    root = ET.parse(route_file).getroot()
    return sum(float(f.get("vehsPerHour", 0)) for f in root.iter("flow"))


def run(run_id, pkg, cfg, extra, note, workdir: Path) -> dict:
    src = HERE / pkg
    dst = workdir / pkg
    if not dst.exists():
        shutil.copytree(src, dst)
        prefix = NETS[pkg][0]
        net = dst / f"{prefix}.net.xml"
        if not net.exists():
            subprocess.run([sumo_bin("netconvert"), "--node-files", f"{prefix}.nod.xml",
                            "--edge-files", f"{prefix}.edg.xml", "--connection-files", f"{prefix}.con.xml",
                            "-o", net.name], cwd=dst, check=True, capture_output=True)
    stats = dst / f"{run_id}.stats.xml"
    cmd = [sumo_bin("sumo"), "-c", cfg, *extra, "--statistic-output", stats.name,
           "--duration-log.statistics", "--no-step-log", "--no-warnings", "--seed", "42"]
    proc = subprocess.run(cmd, cwd=dst, capture_output=True, text=True)
    route = extra[extra.index("-r") + 1] if "-r" in extra else \
        ET.parse(dst / cfg).getroot().find("./input/route-files").get("value")
    row = {"run_id": run_id, "package": pkg, "config": cfg, "overrides": " ".join(extra),
           "route_file": route, "demand_veh_per_h": round(total_demand(dst / route), 1),
           "exit_code": proc.returncode, "note": note}
    if proc.returncode != 0:
        err = [ln for ln in (proc.stderr + proc.stdout).splitlines() if "Error" in ln]
        row["error"] = err[0] if err else proc.stderr.strip()[:200]
        return row
    root = ET.parse(stats).getroot()
    veh = root.find("vehicles").attrib
    tel = root.find("teleports").attrib
    trip = root.find("vehicleTripStatistics").attrib
    row.update({
        "loaded": int(veh["loaded"]), "inserted": int(veh["inserted"]),
        "running_at_end": int(veh["running"]), "waiting_to_insert_at_end": int(veh["waiting"]),
        "teleports": int(tel["total"]), "teleports_jam": int(tel.get("jam", 0)),
        "teleports_yield": int(tel.get("yield", 0)), "collisions": int(root.find("safety").get("collisions", 0)),
        "completed_trips_non_bicycle": int(trip["count"]),
        "mean_time_loss_s": float(trip["timeLoss"]), "mean_depart_delay_s": float(trip["departDelay"]),
        "mean_speed_mps": float(trip["speed"]),
        "inserted_share_of_loaded": round(int(veh["inserted"]) / int(veh["loaded"]), 3),
    })
    return row


def sumo_version() -> str:
    out = subprocess.run([sumo_bin("sumo"), "--version"], capture_output=True, text=True).stdout
    first = out.splitlines()[0] if out else ""
    return first.replace("Eclipse SUMO sumo", "").strip() or "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="run only p5c_base_stable")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    runs = [r for r in RUNS if not args.quick or r[0] == "p5c_base_stable"]
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for r in runs:
            print(f"running {r[0]} ...", flush=True)
            rows.append(run(*r, workdir=Path(tmp)))
            print("   ", {k: rows[-1].get(k) for k in ("exit_code", "inserted", "loaded", "teleports", "error")})
    if not args.quick:
        version = sumo_version()
        for row in rows:
            row["sumo_version"] = version
        cols = []
        for row in rows:  # union of keys, first-seen order
            cols += [k for k in row if k not in cols]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
