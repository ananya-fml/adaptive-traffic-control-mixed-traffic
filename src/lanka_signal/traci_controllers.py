"""Signal controllers for the SUMO/TraCI experiment (NEW code, November 2026).

These classes contain no SUMO calls. Each controller is advanced once per
simulated second with the current per-stage queue lengths (metres) and returns
the signal state for every stage ("G", "y" or "r"). The experiment runner
(``sumo/traci/run_traci_experiment.py``) reads queues from the E2 detectors and
writes the states to the traffic lights.

``QueueProportional`` is a port of the archived VISSIM controller
(``vissim/legacy/original_legacy_controller.py``):

* same cycle-level rule: EMA-smoothed stage queues (alpha 0.5, initialised to 0),
  green budget split in proportion with min/max bounds and a single overflow pass
  (``legacy_split`` reproduces the archived ``proportional_split`` exactly; tested);
* same service rule: stages served largest-smoothed-queue first; after the planned
  green, extend 1 s at a time while the stage's queue exceeds the tail threshold
  and the green is below the maximum; then amber; no all-red.

Deliberate differences from the archived script, all documented in
docs/traci_experiment.md:

1. Queues are LIVE detector jam lengths, not ``QLen(20,1)`` (finding L1).
2. Control continues for the whole run. There is no 81 s all-red remainder or
   all-red cool-down (finding L7).
3. Greens are served in whole seconds, as in the archived script (``while served < target``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

STAGES = ("NS", "EW")


def legacy_split(queues: Dict[str, float], cycle: float, amber: float, all_red: float,
                 g_min: float, g_max: float) -> Dict[str, float]:
    """Exact re-statement of the archived ``proportional_split`` with explicit parameters."""
    n = len(queues)
    usable = cycle - n * (amber + all_red)
    total = sum(max(q, 0.0) for q in queues.values())
    if total <= 0:
        return {k: g_min for k in queues}
    remaining = usable - n * g_min
    greens = {k: g_min + remaining * max(q, 0.0) / total for k, q in queues.items()}
    overflow, capped = 0.0, []
    for k in greens:
        if greens[k] > g_max:
            overflow += greens[k] - g_max
            greens[k] = g_max
            capped.append(k)
    if overflow > 0:
        room = {k: g_max - greens[k] for k in greens if k not in capped and greens[k] < g_max}
        room_sum = sum(room.values())
        if room_sum > 0:
            for k, r in room.items():
                greens[k] += overflow * r / room_sum
    return greens


class Controller:
    name = "base"

    def step(self, t: int, queues: Dict[str, float]) -> Dict[str, str]:  # pragma: no cover
        raise NotImplementedError


@dataclass
class FixedTime(Controller):
    """Pre-timed two-stage plan: EW green, amber, NS green, amber (no all-red)."""
    ew_green: float
    ns_green: float
    amber: float = 3.0
    name: str = "fixed"

    @property
    def cycle(self) -> float:
        return self.ew_green + self.ns_green + 2 * self.amber

    def step(self, t, queues=None):
        c = t % self.cycle
        if c < self.ew_green:
            return {"EW": "G", "NS": "r"}
        if c < self.ew_green + self.amber:
            return {"EW": "y", "NS": "r"}
        if c < self.ew_green + self.amber + self.ns_green:
            return {"EW": "r", "NS": "G"}
        return {"EW": "r", "NS": "y"}


@dataclass
class QueueProportional(Controller):
    """Port of the archived queue-proportional controller with live queue input."""
    cycle: float = 153.0
    amber: float = 3.0
    all_red: float = 0.0
    g_min: float = 10.0
    g_max: float = 80.0
    alpha: float = 0.5
    tail_m: float = 6.0
    name: str = "adaptive"
    # state
    ema: Dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in STAGES})
    order: List[str] = field(default_factory=list)
    targets: Dict[str, float] = field(default_factory=dict)
    stage: str = ""
    phase: str = "start"          # "green" | "amber"
    served: int = 0
    amber_left: int = 0
    log: List[dict] = field(default_factory=list)

    def _new_cycle(self, t, queues):
        for s in STAGES:
            self.ema[s] = self.alpha * queues[s] + (1 - self.alpha) * self.ema[s]
        self.targets = legacy_split(dict(self.ema), self.cycle, self.amber, self.all_red, self.g_min, self.g_max)
        self.order = sorted(STAGES, key=lambda s: self.ema[s], reverse=True)
        self.log.append({"t": t, **{f"ema_{s}": self.ema[s] for s in STAGES},
                         **{f"target_{s}": self.targets[s] for s in STAGES}})

    def _start_green(self, stage):
        self.stage, self.phase, self.served = stage, "green", 0

    def step(self, t, queues):
        if self.phase == "start" or (self.phase == "amber" and self.amber_left == 0 and not self.order):
            self._new_cycle(t, queues)
            self._start_green(self.order.pop(0))
        elif self.phase == "amber" and self.amber_left == 0:
            self._start_green(self.order.pop(0))

        if self.phase == "green":
            target = self.targets[self.stage]
            if self.served < target:
                pass
            elif queues[self.stage] > self.tail_m and self.served < self.g_max:
                pass  # 1 s extension
            else:
                self.log[-1][f"served_{self.stage}"] = self.served
                self.phase, self.amber_left = "amber", int(self.amber)
        if self.phase == "green":
            self.served += 1
            return {s: ("G" if s == self.stage else "r") for s in STAGES}
        # amber
        self.amber_left -= 1
        return {s: ("y" if s == self.stage else "r") for s in STAGES}


def make_controller(name: str) -> Controller:
    """Controllers used in the experiment (see docs/traci_experiment.md)."""
    if name == "fixed_96":       # archived Phase 5C programme
        return FixedTime(ew_green=40, ns_green=50, name=name)
    if name == "fixed_153":      # VISSIM programme (SUMO reading: EW 60 s, NS 87 s)
        return FixedTime(ew_green=60, ns_green=87, name=name)
    if name == "adaptive_96":
        return QueueProportional(cycle=96, name=name)
    if name == "adaptive_153":   # archived parameters
        return QueueProportional(cycle=153, name=name)
    raise ValueError(name)


CONTROLLERS: Sequence[str] = ("fixed_96", "adaptive_96", "fixed_153", "adaptive_153")
