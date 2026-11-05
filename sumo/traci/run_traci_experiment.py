"""Replicated SUMO/TraCI comparison of fixed-time and queue-proportional control.

NEW experiment (November 2026) on the Phase 5C network. These are new SUMO results; they are not a
re-run of, or validation for, the 2025 VISSIM study. See docs/traci_experiment.md.

    pip install eclipse-sumo libsumo traci scipy
    python sumo/traci/run_traci_experiment.py                 # 2 scenarios x 4 controllers x 20 seeds
    python sumo/traci/run_traci_experiment.py --seeds 2       # quick check

Design
------
* Network/demand: archived Phase 5C files, copied to a temp dir (never modified). Each flow's
  regular insertion (``vehsPerHour``) is converted to Poisson arrivals at the same rate
  (``period="exp(rate)"``) so that seeds vary arrivals as well as driver behaviour.
* Scenarios: ``base`` (lanka_base_stable.rou.xml) and ``encroachment`` (lanka_encroachment.rou.xml).
* Controllers: see lanka_signal.traci_controllers.make_controller.
* Queue input: E2 jam length (m) per lane; per approach = max over its two lanes; per stage = sum
  of its two approaches (as VISSIM counters 1+3 and 2+4).
* Run: demand 0-3,600 s; simulation continues to 4,500 s so vehicles can clear.
* Evaluation: vehicles whose *scheduled* departure falls in 600-3,600 s.
  delay = timeLoss + departDelay (s/veh), including vehicles unfinished at 4,500 s.
* Pairing: the same seed is used for every controller, so differences are paired.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from lanka_signal.traci_controllers import CONTROLLERS, make_controller  # noqa: E402

P5C = ROOT / "sumo" / "phase5c"
OUT = ROOT / "data" / "derived"
SCENARIOS = {"base": "lanka_base_stable", "encroachment": "lanka_encroachment"}
TLS = {"EW": ("n8", "n22"), "NS": ("n4", "n20")}
DETECTORS = {"NS": (("q_north_lane0", "q_north_lane1"), ("q_south_lane0", "q_south_lane1")),
             "EW": (("q_east_lane0", "q_east_lane1"), ("q_west_lane0", "q_west_lane1"))}
WARMUP, DEMAND_END, END = 600, 3600, 4500
PAIRS = [("adaptive_96", "fixed_96"), ("adaptive_153", "fixed_153"), ("fixed_153", "fixed_96")]


def sumo_home() -> str:
    """Directory whose bin/ holds sumo and netconvert.

    Importing libsumo can set SUMO_HOME to a data-only folder, so candidates are checked for binaries.
    """
    candidates = []
    try:
        import sumo  # type: ignore  (pip install eclipse-sumo)
        candidates.append(sumo.SUMO_HOME)
    except ImportError:
        pass
    if os.environ.get("SUMO_HOME"):
        candidates.append(os.environ["SUMO_HOME"])
    for c in candidates:
        if Path(c, "bin", "netconvert").exists() or Path(c, "bin", "netconvert.exe").exists():
            return c
    found = shutil.which("netconvert")
    if found:
        return str(Path(found).resolve().parents[1])
    sys.exit("SUMO binaries not found: pip install eclipse-sumo, or set SUMO_HOME")


def prepare(workdir: Path) -> None:
    shutil.copytree(P5C, workdir, dirs_exist_ok=True)
    subprocess.run([str(Path(sumo_home(), "bin", "netconvert")), "--node-files", "lanka_phase5c.nod.xml",
                    "--edge-files", "lanka_phase5c.edg.xml", "--connection-files", "lanka_phase5c.con.xml",
                    "-o", "lanka_phase5c.net.xml"], cwd=workdir, check=True, capture_output=True)
    for stem in SCENARIOS.values():
        txt = (workdir / f"{stem}.rou.xml").read_text()
        txt = re.sub(r'vehsPerHour="([\d.]+)"', lambda m: f'period="exp({float(m.group(1)) / 3600:.8f})"', txt)
        (workdir / f"{stem}.poisson.rou.xml").write_text(txt)


def stage_queues(ls) -> dict:
    return {stage: sum(max(ls.lanearea.getJamLengthMeters(d) for d in approach) for approach in approaches)
            for stage, approaches in DETECTORS.items()}


def one_run(args):
    workdir, scenario, controller_name, seed = args
    import libsumo as ls  # one SUMO instance per process
    workdir = Path(workdir)
    stem = SCENARIOS[scenario]
    tag = f"{scenario}_{controller_name}_{seed}"
    trip, stats = workdir / f"{tag}.trip.xml", workdir / f"{tag}.stats.xml"
    ls.start([str(Path(sumo_home(), "bin", "sumo")), "-c", str(workdir / f"{stem}.sumocfg"),
              "-r", str(workdir / f"{stem}.poisson.rou.xml"), "--seed", str(seed), "--end", str(END),
              "--tripinfo-output", str(trip), "--tripinfo-output.write-unfinished",
              "--statistic-output", str(stats), "--duration-log.statistics",
              "--no-step-log", "--no-warnings", "--verbose", "false"])
    ctrl = make_controller(controller_name)
    q_sum = {"NS": 0.0, "EW": 0.0}
    q_n = 0
    t = 0
    while t < END and (t < DEMAND_END or ls.simulation.getMinExpectedNumber() > 0):
        q = stage_queues(ls)
        states = ctrl.step(t, q)
        for stage, tls_ids in TLS.items():
            for tl in tls_ids:
                ls.trafficlight.setRedYellowGreenState(tl, states[stage] * 2)
        ls.simulationStep()
        t += 1
        if WARMUP <= t < DEMAND_END:
            for s in q:
                q_sum[s] += q[s]
            q_n += 1
    ls.close()

    rows = []
    for tr in ET.parse(trip).getroot().iter("tripinfo"):
        dep, dd = float(tr.get("depart")), float(tr.get("departDelay"))
        sched = dep - dd
        if WARMUP <= sched < DEMAND_END:
            rows.append((float(tr.get("timeLoss")) + dd, float(tr.get("arrival", -1)) > 0, float(tr.get("waitingTime"))))
    root = ET.parse(stats).getroot()
    out = {
        "scenario": scenario, "controller": controller_name, "seed": seed,
        "n_vehicles": len(rows),
        "mean_delay_s": sum(r[0] for r in rows) / len(rows),
        "mean_waiting_s": sum(r[2] for r in rows) / len(rows),
        "share_completed": sum(r[1] for r in rows) / len(rows),
        "mean_queue_ns_m": q_sum["NS"] / q_n, "mean_queue_ew_m": q_sum["EW"] / q_n,
        "teleports": int(root.find("teleports").get("total")),
        "collisions": int(root.find("safety").get("collisions")),
        "not_inserted_at_end": int(root.find("vehicles").get("waiting")),
        "sim_end_s": t,
    }
    if hasattr(ctrl, "log") and ctrl.log:
        served = [r for r in ctrl.log if "served_NS" in r and "served_EW" in r]
        if served:
            out["mean_green_ns_s"] = sum(r["served_NS"] for r in served) / len(served)
            out["mean_green_ew_s"] = sum(r["served_EW"] for r in served) / len(served)
    else:
        out["mean_green_ns_s"], out["mean_green_ew_s"] = ctrl.ns_green, ctrl.ew_green
    for f in (trip, stats):
        f.unlink(missing_ok=True)
    return out


def summarise(runs):
    import pandas as pd
    from scipy import stats

    df = pd.DataFrame(runs)
    rows = []
    for sc in df.scenario.unique():
        for a, b in PAIRS:
            x = df[(df.scenario == sc) & (df.controller == a)].set_index("seed")
            y = df[(df.scenario == sc) & (df.controller == b)].set_index("seed")
            common = x.index.intersection(y.index)
            for metric in ("mean_delay_s", "mean_queue_ns_m", "mean_queue_ew_m", "share_completed"):
                d = (x.loc[common, metric] - y.loc[common, metric]).astype(float)
                n = len(d)
                mean, sd = d.mean(), d.std(ddof=1) if n > 1 else float("nan")
                half = stats.t.ppf(0.975, n - 1) * sd / n ** 0.5 if n > 1 else float("nan")
                p = stats.ttest_rel(x.loc[common, metric], y.loc[common, metric]).pvalue if n > 1 else float("nan")
                base = y.loc[common, metric].mean()
                rows.append({"scenario": sc, "comparison": f"{a} vs {b}", "metric": metric, "n_seeds": n,
                             "mean_a": x.loc[common, metric].mean(), "mean_b": base,
                             "mean_diff": mean, "ci95_low": mean - half, "ci95_high": mean + half,
                             "pct_change": 100 * mean / base if base else float("nan"), "p_paired_t": p})
    return df, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 1)))
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--controllers", default=",".join(CONTROLLERS))
    ap.add_argument("--out-prefix", default="traci")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        prepare(Path(tmp))
        jobs = [(tmp, sc, c, 1000 + i) for sc in a.scenarios.split(",") for i in range(a.seeds)
                for c in a.controllers.split(",")]
        print(f"{len(jobs)} runs on {a.workers} worker(s)", flush=True)
        ctx = mp.get_context("spawn")
        with ctx.Pool(a.workers, maxtasksperchild=1) as pool:
            runs = []
            for i, r in enumerate(pool.imap_unordered(one_run, jobs), 1):
                runs.append(r)
                print(f"[{i}/{len(jobs)}] {r['scenario']} {r['controller']} seed {r['seed']}: "
                      f"delay {r['mean_delay_s']:.1f} s", flush=True)
    df, summary = summarise(runs)
    OUT.mkdir(parents=True, exist_ok=True)
    df.sort_values(["scenario", "controller", "seed"]).to_csv(OUT / f"{a.out_prefix}_runs.csv", index=False)
    summary.to_csv(OUT / f"{a.out_prefix}_paired.csv", index=False)
    print(summary[summary.metric == "mean_delay_s"].round(3).to_string())


if __name__ == "__main__":
    main()
