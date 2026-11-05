"""Lanka VISSIM: paired fixed-time, queue-proportional and movement Max-Pressure trials.

Requires Windows, licensed PTV Vissim with COM support, Python + pywin32.
Run: python experiment.py --config config.json
Never infer link IDs: configure the network's actual approach and exit links first.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

METHODS = ("fixed", "queue", "max_pressure")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def validate(c):
    p = Path(c["network_inpx"])
    if not p.is_file():
        raise ValueError(f"Set network_inpx to an existing .inpx file: {p}")
    if c.get("layout_layx") and not Path(c["layout_layx"]).is_file():
        raise ValueError("layout_layx does not exist")
    if c["total_sec"] < c["eval_end_sec"] or not 0 <= c["eval_start_sec"] < c["eval_end_sec"]:
        raise ValueError("Evaluation times must lie within simulation duration")
    if c["sim_res"] != 10:
        raise ValueError("This experiment is designed for SimRes=10; adapt run_one_second if changing")
    stages = c["stages"]
    if len(stages) != 2 or len({s["name"] for s in stages}) != 2:
        raise ValueError("Supply exactly two uniquely named stages (NS/EW)")
    names = {s["name"] for s in stages}
    if any(not s["signal_groups"] or not s["upstream_links"] for s in stages):
        raise ValueError("Every stage needs signal_groups and upstream_links")
    all_sgs = [n for s in stages for n in s["signal_groups"]]
    if len(set(all_sgs)) != len(all_sgs):
        raise ValueError("Signal group cannot belong to two stages")
    all_links = [x for s in stages for x in s["upstream_links"]]
    if len(set(all_links)) != len(all_links):
        raise ValueError("Upstream links must be assigned to exactly one stage")
    if not c["movements"]:
        raise ValueError("Max-Pressure requires movement definitions")
    movement_groups = defaultdict(float)
    for m in c["movements"]:
        if m["stage"] not in names or m["upstream_link"] not in next(s["upstream_links"] for s in stages if s["name"] == m["stage"]):
            raise ValueError(f"Movement doesn't match its stage/upstream link: {m}")
        if m["downstream_link"] == m["upstream_link"]:
            raise ValueError("Upstream and downstream cannot be same link")
        if not 0 < m["turn_fraction"] <= 1 or m["saturation_veh_per_sec"] <= 0:
            raise ValueError("Invalid turn fraction or saturation discharge rate")
        movement_groups[m["upstream_link"]] += m["turn_fraction"]
    for link in all_links:
        if abs(movement_groups[link] - 1) > 0.02:
            raise ValueError(f"Turning fractions from upstream link {link} must sum to 1, got {movement_groups[link]:.3f}")
    t = c["timing"]
    if t["min_green_sec"] <= 0 or t["max_green_sec"] <= t["min_green_sec"] or t["amber_sec"] < 1 or t["all_red_sec"] < 1:
        raise ValueError("Check min/max green, amber and all-red safety settings")
    effective = t["fixed_cycle_sec"] - len(stages) * (t["amber_sec"] + t["all_red_sec"])
    if not math.isclose(sum(t["fixed_greens_sec"].values()), effective, abs_tol=1e-7):
        raise ValueError(f"Fixed greens must sum to cycle minus intergreens = {effective:.1f}s")
    if set(t["fixed_greens_sec"]) != names:
        raise ValueError("fixed_greens_sec keys must match stage names")
    for value in t["fixed_greens_sec"].values():
        if not float(value).is_integer():
            raise ValueError("fixed_greens_sec must be whole seconds with the 1-second policy step")
        if not t["min_green_sec"] <= value <= t["max_green_sec"]:
            raise ValueError("Fixed greens violate min/max limits")
    if not len(c["random_seeds"]) or len(set(c["random_seeds"])) != len(c["random_seeds"]):
        raise ValueError("Supply nonempty, unique random seeds")
    if c["queue_upstream_window_m"] <= 0 or c["queue_downstream_window_m"] <= 0:
        raise ValueError("Queue windows must be positive")


def safe_att(obj, attribute):
    try:
        return obj.AttValue(attribute)
    except Exception as ex:
        raise RuntimeError(f"VISSIM COM cannot read {attribute!r}: {ex}") from ex


class LiveSensors:
    """Count stopped vehicles in chosen link segments (NOT evaluated QLen averages).

    For each upstream link, inspect last N m before link end. For each downstream
    link, inspect first M m. Both must be calibrated to actual intersection geometry.
    """
    def __init__(self, vissim, cfg):
        self.c = cfg
        ids = set()
        for s in cfg["stages"]:
            ids.update(s["upstream_links"])
        for m in cfg["movements"]:
            ids.add(m["downstream_link"])
        self.links = {}
        self.lengths = {}
        for no in sorted(ids):
            obj = vissim.Net.Links.ItemByKey(int(no))
            if obj is None:
                raise ValueError(f"Link {no} not found in VISSIM network")
            self.links[no] = obj
            self.lengths[no] = float(safe_att(obj, "Length2D"))
            if self.lengths[no] <= 0:
                raise ValueError(f"Link {no} has nonpositive length")
        self.upstream_ids = {k for s in cfg["stages"] for k in s["upstream_links"]}
        self.downstream_ids = {m["downstream_link"] for m in cfg["movements"]}
        self.stopped_mps = cfg["stopped_speed_kmh"] / 3.6
        self.last_seen_stopped = {}
        self.stop_events = 0
        self.exit_first_seen = set()
        self.exit_entries = 0

    def sample(self, count_events=False):
        up = defaultdict(int)
        down = defaultdict(int)
        qlength = defaultdict(float)
        active_stop_ids = set()
        active_down_ids = set()
        for lid, link in self.links.items():
            length = self.lengths[lid]
            for veh in link.Vehs.GetAll():
                # Veh.Pos is in metres; Veh.Speed is km/h in default metric networks.
                try:
                    pos = float(safe_att(veh, "Pos"))
                    speed_kmh = float(safe_att(veh, "Speed"))
                    veh_id = int(safe_att(veh, "No"))
                except (TypeError, ValueError) as ex:
                    raise RuntimeError(f"Bad vehicle data on link {lid}: {ex}") from ex
                stopped = speed_kmh <= self.c["stopped_speed_kmh"]
                if lid in self.upstream_ids and pos >= max(0.0, length - self.c["queue_upstream_window_m"]):
                    if stopped:
                        up[lid] += 1
                        qlength[lid] = max(qlength[lid], length - pos)
                        active_stop_ids.add(veh_id)
                if lid in self.downstream_ids and pos <= self.c["queue_downstream_window_m"]:
                    if stopped:
                        down[lid] += 1
                    active_down_ids.add((lid, veh_id))
        if count_events:
            # These are one-second sampled proxies, NOT VISSIM's official Stops/Throughput metrics.
            for vid in active_stop_ids:
                if not self.last_seen_stopped.get(vid, False):
                    self.stop_events += 1
            self.last_seen_stopped = {vid: True for vid in active_stop_ids}
            new_entries = active_down_ids - self.exit_first_seen
            self.exit_entries += len(new_entries)
            self.exit_first_seen.update(active_down_ids)
        return {"up": dict(up), "down": dict(down), "length": dict(qlength)}


def proportional_greens(stage_loads, cfg):
    """Project queue-proportional weights onto bounded greens and fixed cycle budget."""
    t = cfg["timing"]
    names = [s["name"] for s in cfg["stages"]]
    n = len(names)
    budget = t["fixed_cycle_sec"] - n * (t["amber_sec"] + t["all_red_sec"])
    minimum, maximum = t["min_green_sec"], t["max_green_sec"]
    if not n * minimum <= budget <= n * maximum:
        raise ValueError("Cycle green budget infeasible under min/max")
    g = {name: minimum for name in names}
    remaining = budget - n * minimum
    weights = {name: max(0.0, stage_loads.get(name, 0.0)) for name in names}
    if sum(weights.values()) <= 1e-12:
        weights = {name: 1.0 for name in names}
    available = set(names)
    while remaining > 1e-9 and available:
        total_weight = sum(weights[k] for k in available)
        proposed = {k: remaining * (weights[k] / total_weight if total_weight else 1 / len(available)) for k in available}
        capped = [k for k in available if g[k] + proposed[k] >= maximum - 1e-9]
        if not capped:
            for k in available:
                g[k] += proposed[k]
            break
        for k in capped:
            extra = maximum - g[k]
            g[k] = maximum
            remaining -= extra
            available.remove(k)
    # Signal decisions are made at 1-second boundaries. Round allocation while
    # preserving the exact per-cycle green budget and integer safety bounds.
    floor_g = {k: int(math.floor(g[k])) for k in names}
    leftover = int(round(budget - sum(floor_g.values())))
    for k in sorted(names, key=lambda k: (g[k] - floor_g[k]), reverse=True):
        if leftover <= 0:
            break
        if floor_g[k] < maximum:
            floor_g[k] += 1
            leftover -= 1
    if leftover:
        raise ValueError("Unable to integer-round cycle green allocation")
    return floor_g


def stage_queue_load(snapshot, cfg, stage_name):
    ids = next(s["upstream_links"] for s in cfg["stages"] if s["name"] == stage_name)
    # In units of metres, like the original approach. These are instantaneous proxies.
    return sum(snapshot["length"].get(i, 0.0) for i in ids)


def pressure(snapshot, cfg):
    """Movement-pressure stage weight: sum_{i,j} s_ij * r_ij * (q_i - q_j).

    q=stopped vehicle count per calibrated sensing region, s=discharge veh/s,
    r=turn fraction. This is a finite-sensing-zone *approximation* to classical MP.
    Negative terms are retained, so blocked exits can reduce stage pressure.
    """
    totals = {s["name"]: 0.0 for s in cfg["stages"]}
    for m in cfg["movements"]:
        qi = snapshot["up"].get(m["upstream_link"], 0)
        qj = snapshot["down"].get(m["downstream_link"], 0)
        totals[m["stage"]] += m["saturation_veh_per_sec"] * m["turn_fraction"] * (qi - qj)
    return totals


class SignalController:
    """Green -> amber -> all-red -> green, with minimum clearance always preserved."""
    def __init__(self, vissim, cfg, method):
        self.cfg, self.method = cfg, method
        sc = vissim.Net.SignalControllers.ItemByKey(int(cfg["signal_controller_id"]))
        if sc is None:
            raise ValueError("Signal controller not found")
        self.groups = {}
        for s in cfg["stages"]:
            self.groups[s["name"]] = [sc.SGs.ItemByKey(int(n)) for n in s["signal_groups"]]
            if any(obj is None for obj in self.groups[s["name"]]):
                raise ValueError("Signal group not found")
        self.names = [s["name"] for s in cfg["stages"]]
        self.current = None
        self.next_stage = self.names[0]
        self.mode = "all_red"
        self.elapsed = 0.0
        self.green_elapsed = 0.0
        self.red_elapsed = {k: 0.0 for k in self.names}
        self.cycle_greens = dict(cfg["timing"]["fixed_greens_sec"])
        self.ema = {k: 0.0 for k in self.names}
        self.cycle_no = 0
        self.switch_count = 0
        self.last_score = {k: 0.0 for k in self.names}
        self._all_red()

    def _all_red(self):
        for objs in self.groups.values():
            for obj in objs:
                obj.SetAttValue("SigState", 1)

    def _start_green(self, stage):
        self._all_red()
        for obj in self.groups[stage]:
            obj.SetAttValue("SigState", 3)
        self.current = stage
        self.mode = "green"
        self.elapsed = 0.0
        self.green_elapsed = 0.0
        self.red_elapsed[stage] = 0.0

    def _start_amber(self, successor):
        for obj in self.groups[self.current]:
            obj.SetAttValue("SigState", 4)
        self.next_stage = successor
        self.mode = "amber"
        self.elapsed = 0.0
        self.switch_count += 1

    def scores(self, snap):
        if self.method == "max_pressure":
            self.last_score = pressure(snap, self.cfg)
        else:
            self.last_score = {k: stage_queue_load(snap, self.cfg, k) for k in self.names}
        return self.last_score

    def _begin_new_cycle(self, snap):
        if self.method == "fixed":
            self.cycle_greens = dict(self.cfg["timing"]["fixed_greens_sec"])
        else:
            loads = {k: stage_queue_load(snap, self.cfg, k) for k in self.names}
            alpha = self.cfg["ema_alpha"]
            for k in self.names:
                self.ema[k] = alpha * loads[k] + (1 - alpha) * self.ema[k]
            self.cycle_greens = proportional_greens(self.ema, self.cfg)
        self.cycle_no += 1

    def update(self, snap, dt=1.0):
        t = self.cfg["timing"]
        self.elapsed += dt
        for k in self.names:
            if k != self.current or self.mode != "green":
                self.red_elapsed[k] += dt
        if self.mode == "amber":
            if self.elapsed >= t["amber_sec"] - 1e-9:
                self._all_red()
                self.mode = "all_red"
                self.elapsed = 0.0
            return
        if self.mode == "all_red":
            if self.elapsed >= t["all_red_sec"] - 1e-9:
                if self.current is None:
                    if self.method == "max_pressure":
                        self.next_stage = max(self.names, key=lambda k: self.scores(snap)[k])
                    else:
                        self._begin_new_cycle(snap)
                self._start_green(self.next_stage)
            return
        self.green_elapsed += dt
        if self.method in ("fixed", "queue"):
            if self.green_elapsed + 1e-9 >= self.cycle_greens[self.current]:
                next_idx = (self.names.index(self.current) + 1) % len(self.names)
                successor = self.names[next_idx]
                if successor == self.names[0]:
                    self._begin_new_cycle(snap)
                self._start_amber(successor)
            return
        scores = self.scores(snap)
        other = next(k for k in self.names if k != self.current)
        if self.green_elapsed < t["min_green_sec"] - 1e-9:
            return
        # Anti-starvation: serve the opposing stage after a maximum red duration.
        force_other = self.red_elapsed[other] >= t["max_red_sec"]
        time_limit = self.green_elapsed >= t["max_green_sec"]
        improves = scores[other] > scores[self.current] + t["pressure_hysteresis"]
        if force_other or time_limit or (self.green_elapsed >= t["decision_interval_sec"] and improves):
            self._start_amber(other)


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def run_one(cfg, scenario, method, seed, outdir):
    import win32com.client as com  # Windows only
    # Fresh Vissim process/network state for every replicate; never share live controllers.
    vissim = com.DispatchEx("Vissim.Vissim")
    try:
        vissim.LoadNet(str(Path(scenario["network_inpx"]).resolve()))
        if cfg.get("layout_layx"):
            vissim.LoadLayout(str(Path(cfg["layout_layx"]).resolve()))
        sim = vissim.Simulation
        sim.SetAttValue("SimRes", cfg["sim_res"])
        sim.SetAttValue("SimPeriod", cfg["total_sec"])
        sim.SetAttValue("RandSeed", int(seed))
        sim.SetAttValue("SimBreakAt", 0)
        sensors = LiveSensors(vissim, cfg)
        controller = SignalController(vissim, cfg, method)
        trace = []
        sums = defaultdict(float)
        samples = 0
        max_queue = 0
        initial_stops = sensors.stop_events
        # At each second, first advance by 10 Vissim ticks, then read the live state
        # and update signals for the next second. Control decisions use no future data.
        for second in range(1, cfg["total_sec"] + 1):
            for _ in range(cfg["sim_res"]):
                sim.RunSingleStep()
            in_eval = cfg["eval_start_sec"] <= second < cfg["eval_end_sec"]
            snap = sensors.sample(count_events=in_eval)
            controller.update(snap, dt=1.0)
            if in_eval:
                samples += 1
                n_stop = sum(snap["up"].values())
                sums["stopped_vehicle_seconds"] += n_stop
                total_qm = sum(snap["length"].values())
                sums["queue_m_seconds"] += total_qm
                max_queue = max(max_queue, total_qm)
                sums["downstream_stopped_vehicle_seconds"] += sum(snap["down"].values())
                if second % cfg["trace_every_sec"] == 0:
                    trace.append({"second": second, "stage": controller.current,
                                  "signal_mode": controller.mode,
                                  "upstream_stopped_vehicles": n_stop,
                                  "upstream_queue_length_sum_m": round(total_qm, 3),
                                  "downstream_stopped_vehicles": sum(snap["down"].values()),
                                  "NS_pressure": round(pressure(snap, cfg).get("NS", float("nan")), 4),
                                  "EW_pressure": round(pressure(snap, cfg).get("EW", float("nan")), 4)})
        sim.Stop()
        prefix = f"{scenario['name']}_{method}_seed{seed}"
        write_csv(outdir / f"{prefix}_trace.csv", trace,
                  ["second", "stage", "signal_mode", "upstream_stopped_vehicles",
                   "upstream_queue_length_sum_m", "downstream_stopped_vehicles", "NS_pressure", "EW_pressure"])
        return {"scenario": scenario["name"], "method": method, "seed": seed,
                "samples": samples,
                "mean_stopped_upstream_vehicles": sums["stopped_vehicle_seconds"] / samples,
                "mean_upstream_queue_length_sum_m": sums["queue_m_seconds"] / samples,
                "max_upstream_queue_length_sum_m": max_queue,
                "mean_stopped_downstream_vehicles": sums["downstream_stopped_vehicle_seconds"] / samples,
                "sampled_stop_onsets_proxy": sensors.stop_events - initial_stops,
                "sampled_downstream_link_entries_proxy": sensors.exit_entries,
                "signal_changes": controller.switch_count}
    finally:
        try:
            vissim.Exit()
        except Exception:
            pass


def summarize(rows, outdir):
    cols = ["mean_stopped_upstream_vehicles", "mean_upstream_queue_length_sum_m",
            "max_upstream_queue_length_sum_m", "mean_stopped_downstream_vehicles",
            "sampled_stop_onsets_proxy", "sampled_downstream_link_entries_proxy", "signal_changes"]
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["scenario"], row["method"])].append(row)
    summary = []
    for (scenario, method), data in sorted(grouped.items()):
        d = {"scenario": scenario, "method": method, "n_seeds": len(data)}
        for metric in cols:
            values = [float(r[metric]) for r in data]
            d[metric + "_mean"] = statistics.mean(values)
            d[metric + "_sd"] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary.append(d)
    write_csv(outdir / "summary.csv", summary, list(summary[0]) if summary else [])
    # Paired % reduction vs fixed on each SAME seed, then average across seeds.
    lookup = {(r["scenario"], r["method"], r["seed"]): r for r in rows}
    comparisons = []
    for r in rows:
        if r["method"] == "fixed":
            continue
        base = lookup.get((r["scenario"], "fixed", r["seed"]))
        if base is None:
            raise RuntimeError("Missing same-seed fixed baseline")
        comparison = {"scenario": r["scenario"], "method": r["method"], "seed": r["seed"]}
        for metric in cols[:4]:
            denominator = float(base[metric])
            comparison[metric + "_reduction_pct"] = (100 * (denominator - float(r[metric])) / denominator if denominator else "")
        comparisons.append(comparison)
    write_csv(outdir / "paired_comparisons.csv", comparisons,
              list(comparisons[0]) if comparisons else [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    scenarios = cfg.get("scenarios") or [{"name": "base", "network_inpx": cfg["network_inpx"]}]
    outdir = Path(cfg["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario in scenarios:
        local = dict(cfg, network_inpx=scenario["network_inpx"])
        validate(local)
        for seed in cfg["random_seeds"]:
            for method in METHODS:
                print(f"Scenario={scenario['name']}  seed={seed}  controller={method}", flush=True)
                row = run_one(local, scenario, method, seed, outdir)
                rows.append(row)
                write_csv(outdir / "replicates.csv", rows, list(rows[0]))
    summarize(rows, outdir)
    print(f"Finished. Results: {outdir.resolve()}")


if __name__ == "__main__":
    main()
