# SUMO/TraCI controller experiment (new, November 2026)

`run_traci_experiment.py` drives the Phase 5C SUMO network through TraCI (`libsumo`) with four
controllers and 20 paired random seeds per scenario. The controllers are in
[`src/lanka_signal/traci_controllers.py`](../../src/lanka_signal/traci_controllers.py):

| Controller | What it is |
|---|---|
| `fixed_96` | Archived Phase 5C programme: EW 40 s + 3 s amber, NS 50 s + 3 s amber |
| `fixed_153` | VISSIM programme as read by the SUMO reconstruction: EW 60 s, NS 87 s, 3 s ambers |
| `adaptive_96` | Port of the archived queue-proportional controller, 96 s nominal cycle |
| `adaptive_153` | Same, with the archived 153 s parameters |

```bash
pip install eclipse-sumo==1.28.0 libsumo==1.28.0 traci==1.28.0 scipy
python sumo/traci/run_traci_experiment.py              # 160 runs, ~25 min on 2 cores
python sumo/traci/run_traci_experiment.py --seeds 2    # quick check
python analysis/make_figures.py                        # regenerates figures/traci_delay_differences_*.png
```

Outputs: `data/derived/traci_runs.csv` (one row per run) and `data/derived/traci_paired.csv`
(paired differences with 95% confidence intervals).

**These are new SUMO results.** They are not a re-run of, or validation for, the 2025 VISSIM study.
Design, results and limitations: [`docs/traci_experiment.md`](../../docs/traci_experiment.md).
