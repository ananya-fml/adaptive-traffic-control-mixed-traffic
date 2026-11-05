"""Revised green-allocation helpers written during the 2026 audit.

STATUS: new code. It has NOT been run in VISSIM or SUMO and produced no results.
It exists to make the defects found in the legacy helpers explicit and testable.

Differences from the legacy ``proportional_split`` (see docs/legacy_code_audit.md):

* Parameters are explicit arguments, not module globals.
* Missing / non-numeric queue readings are reported (``ValueError``) instead of
  silently becoming ``None`` and crashing later.
* When every queue is zero the green budget is split equally, so the cycle stays
  at its nominal length (legacy: every stage gets ``min_green`` and the cycle
  collapses from 153 s to 26 s).
* Overflow redistribution is iterated until no stage exceeds ``max_green``.
* Greens are rounded to whole control steps while preserving the exact budget,
  so the realised cycle equals the nominal cycle (legacy: 73.5 s targets are
  served as 74 s, so cycles drift).
"""
from __future__ import annotations

import math
from typing import Mapping


def green_budget(cycle: float, n_stages: int, amber: float, all_red: float) -> float:
    """Green time available per cycle after intergreens."""
    return cycle - n_stages * (amber + all_red)


def effective_green_range(cycle, n_stages, amber, all_red, g_min, g_max):
    """Closed-form [lo, hi] range a single stage's green can take.

    For two stages with the legacy settings (153, 2, 3, 0, 10, 80) this is
    (67.0, 80.0): the opposing stage can absorb at most ``g_max``.
    """
    budget = green_budget(cycle, n_stages, amber, all_red)
    lo = max(g_min, budget - (n_stages - 1) * g_max)
    hi = min(g_max, budget - (n_stages - 1) * g_min)
    if lo > hi:
        raise ValueError("Infeasible min/max green for this cycle")
    return lo, hi


def proportional_split_revised(
    queues: Mapping[str, float],
    *,
    cycle: float = 153.0,
    amber: float = 3.0,
    all_red: float = 0.0,
    g_min: float = 10.0,
    g_max: float = 80.0,
    step: float = 1.0,
) -> dict:
    """Budget-preserving, bounded, queue-proportional green split."""
    names = list(queues)
    n = len(names)
    if n == 0:
        raise ValueError("No stages")
    clean = {}
    for k, q in queues.items():
        if q is None or not isinstance(q, (int, float)) or math.isnan(q):
            raise ValueError(f"Missing queue reading for stage {k!r}: {q!r}")
        clean[k] = max(float(q), 0.0)

    budget = green_budget(cycle, n, amber, all_red)
    if not (n * g_min <= budget <= n * g_max):
        raise ValueError("Green budget infeasible under min/max green")

    total = sum(clean.values())
    weights = {k: (clean[k] / total if total > 0 else 1.0 / n) for k in names}
    greens = {k: g_min for k in names}
    free = set(names)
    remaining = budget - n * g_min
    while remaining > 1e-9 and free:
        w_sum = sum(weights[k] for k in free)
        if w_sum > 0:
            share = {k: remaining * weights[k] / w_sum for k in free}
        else:  # remaining stages all have zero queue: share equally
            share = {k: remaining / len(free) for k in free}
        capped = [k for k in free if greens[k] + share[k] > g_max + 1e-9]
        if not capped:
            for k in free:
                greens[k] += share[k]
            remaining = 0.0
            break
        for k in capped:
            remaining -= g_max - greens[k]
            greens[k] = g_max
            free.discard(k)

    # Round to control steps without changing the total.
    units = {k: math.floor(greens[k] / step + 1e-9) for k in names}
    leftover = int(round(budget / step)) - sum(units.values())
    order = sorted(names, key=lambda k: greens[k] / step - units[k], reverse=True)
    i = 0
    while leftover > 0:
        k = order[i % n]
        if (units[k] + 1) * step <= g_max + 1e-9:
            units[k] += 1
            leftover -= 1
        i += 1
        if i > 10 * n and leftover > 0:
            raise ValueError("Cannot round allocation within bounds")
    return {k: units[k] * step for k in names}
