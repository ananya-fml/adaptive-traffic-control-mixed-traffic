"""Replay the UNMODIFIED legacy controller's main() against a fake VISSIM.

No traffic is simulated. Each case fixes what ``QLen(SIMULATION_NO, TIME_INTERVAL)``
returns, which isolates the controller's timing behaviour:

* how long each stage's green actually lasts,
* how long cycles actually are (vs the nominal 153 s),
* when the script finishes relative to the 4,500 s SimPeriod.

    python analysis/replay_legacy_controller.py

Writes data/derived/legacy_replay.csv and data/derived/legacy_allocation_curve.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lanka_signal import legacy_logic as L  # noqa: E402
from lanka_signal.fake_vissim import green_intervals, replay_legacy_main  # noqa: E402

OUT = ROOT / "data" / "derived"
NS, EW = (1, 3), (2, 4)  # queue counters per stage, as in the legacy STAGES

CASES = {
    "constant 12 m on every counter (QLen above 6 m tail threshold)":
        lambda qc, t, a: 12.0,
    "constant 3 m on every counter (below tail threshold)":
        lambda qc, t, a: 3.0,
    "NS 10 m / EW 2 m per counter, constant (below/above threshold mix)":
        lambda qc, t, a: 10.0 if qc in NS else 2.0,
    "NS 4 m / EW 1 m per counter, constant (both below threshold)":
        lambda qc, t, a: 4.0 if qc in NS else 1.0,
    "zero on every counter (e.g. no queue result available as 0)":
        lambda qc, t, a: 0.0,
    "None on every counter (attribute has no value yet)":
        lambda qc, t, a: None,
}


def summarise(name, fn) -> dict:
    try:
        fake = replay_legacy_main(fn)
    except Exception as exc:  # the legacy code's own failure is the finding
        return {"case": name, "outcome": f"{type(exc).__name__}: {exc}"}
    ew = green_intervals(fake.sig_log, 1)
    ns = green_intervals(fake.sig_log, 2)
    starts = sorted(a for a, _ in ew + ns)
    # one "cycle" = both stages served once; legacy serves stages in pairs
    pairs = [starts[i + 2] - starts[i] for i in range(0, len(starts) - 2, 2)]
    return {
        "case": name, "outcome": "completed",
        "ew_green_s_median": pd.Series([b - a for a, b in ew]).median(),
        "ns_green_s_median": pd.Series([b - a for a, b in ns]).median(),
        "cycles_served": len(ew),
        "cycle_s_median": pd.Series(pairs).median() if pairs else None,
        "first_green_s": starts[0], "last_green_end_s": max(b for _, b in ew + ns),
        "script_end_s": round(fake.clock.second, 1),
        "seconds_beyond_simperiod_4500": round(fake.clock.overrun_ticks / L.PARAMETERS["SIM_RES"], 1),
        "qlen_attribute_read": fake.qlen_reads[0][2] if fake.qlen_reads else None,
    }


def allocation_curve() -> pd.DataFrame:
    rows = []
    for i in range(0, 1001):
        share = i / 1000
        g = L.proportional_split({"NS": share, "EW": 1 - share})
        rows.append({"ns_queue_share": share, "ns_green_s": g["NS"], "ew_green_s": g["EW"]})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([summarise(n, f) for n, f in CASES.items()])
    df.to_csv(OUT / "legacy_replay.csv", index=False)
    allocation_curve().to_csv(OUT / "legacy_allocation_curve.csv", index=False)
    print(df.to_string())


if __name__ == "__main__":
    main()
