"""Extract simulation, evaluation and signal-control settings from the archived
VISSIM .inpx models (not distributed; see data/raw/README.md).

    python analysis/audit_inpx.py --raw results=data/raw/results --raw ug_results=data/raw/ug_results

Writes data/derived/inpx_settings.csv (one row per scenario) and
data/derived/fixed_time_programme.csv (raw signal-programme commands).
Only settings are extracted; no geometry or proprietary model content is copied.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "derived"


def attrs(tag: str) -> dict:
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def first(pattern: str, text: str) -> dict:
    m = re.search(pattern, text)
    return attrs(m.group(0)) if m else {}


def scan(label: str, inpx: Path, rows: list, cmds: list) -> None:
    s = inpx.read_text(encoding="utf-8")
    scen = inpx.parent.name
    sim = first(r"<simulation [^>]*>", s)
    ev = s[s.find("<evaluation "): s.find("</evaluation>")]
    row = {
        "archive": label, "scenario": scen, "file": inpx.name,
        "sha256": hashlib.sha256(inpx.read_bytes()).hexdigest(),
        "signal_heads": len(re.findall(r"<signalHead ", s)),
        "vissim_version": first(r"<network [^>]*>", s).get("vissimVersion"),
        "sim_period_s": sim.get("simPeriod"), "sim_res_steps_per_s": sim.get("simRes"),
        "rand_seed": sim.get("randSeed"), "rand_seed_incr": sim.get("randSeedIncr"),
        "num_runs": sim.get("numRuns"),
        "keep_prev_results": first(r"<evaluation [^>]*>", s).get("keepPrevResults"),
        "vehicle_input_total_veh_per_h": sum(
            float(v) for v in re.findall(r'<timeIntervalVehVolume [^>]*volume="([\d.]+)"', s)),
    }
    for key in ("nodeResults", "vehNetPerf", "dataColl", "queues", "delays"):
        a = first(rf"<{key} [^>]*>", ev)
        row[f"{key}_window"] = f"{a.get('fromTime')}-{a.get('toTime')}"
        row[f"{key}_interval_s"] = a.get("interval")
    row["queue_counters"] = "; ".join(
        f"{a['no']}:link{a['link']}@{float(a['pos']):.0f}m:{a['name'].strip()}"
        for a in map(attrs, re.findall(r"<queueCounter [^>]*>", s)))
    row["signal_head_lane_to_sg"] = "; ".join(
        f"lane {a['lane']}->SG{a['sg'].split()[-1]}"
        for a in map(attrs, re.findall(r"<signalHead [^>]*>", s)))
    sc = first(r"<signalController [^>]*>", s)
    row["signal_controller_type"] = sc.get("type")
    row["signal_groups"] = "; ".join(
        f"SG{a['no']}:amber={a['amber']},minGreen={a['minGreen']},actuation={a['actuationType']}"
        for a in map(attrs, re.findall(r"<signalGroup [^>]*>", s)))
    supply = base64.b64decode(sc["intSupplyData"]).decode("utf-8")
    prog = first(r"<prog [^>]*>", supply)
    row["programme_cycle_s"] = int(prog["cycletime"]) / 1000
    row["intergreens"] = "; ".join(
        f"{a['clearingsg']}->{a['enteringsg']}={a['value']}"
        for a in map(attrs, re.findall(r"<intergreen [^>]*>", supply)))
    for sg_id, body in re.findall(r'<sg sg_id="(\d+)"[^>]*>(.*?)</sg>', supply, flags=re.S):
        for a in map(attrs, re.findall(r"<cmd [^>]*>", body)):
            cmds.append({"archive": label, "scenario": scen, "signal_group": int(sg_id),
                         "command": {"1": "RED", "3": "GREEN"}.get(a["display"], a["display"]),
                         "begin_s": int(a["begin"]) / 1000, "duration_s": None})
        for a in map(attrs, re.findall(r"<fixedstate [^>]*>", body)):
            cmds.append({"archive": label, "scenario": scen, "signal_group": int(sg_id),
                         "command": "AMBER (fixed state)", "begin_s": None,
                         "duration_s": int(a["duration"]) / 1000})
    rows.append(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="append", required=True,
                    help="LABEL=PATH to an extracted results folder; repeatable")
    sources = [r.split("=", 1) if "=" in r else (Path(r).name, r) for r in ap.parse_args().raw]
    rows, cmds = [], []
    for label, root in sources:
        for inpx in sorted(Path(root).glob("*/*.inpx")):
            scan(label, inpx, rows, cmds)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "inpx_settings.csv", index=False)
    pd.DataFrame(cmds).to_csv(OUT / "fixed_time_programme.csv", index=False)
    print(pd.DataFrame(rows)[["archive", "scenario", "vissim_version", "signal_heads",
                              "sim_res_steps_per_s", "keep_prev_results"]].to_string())


if __name__ == "__main__":
    main()
