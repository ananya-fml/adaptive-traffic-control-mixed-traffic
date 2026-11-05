# Limitations and reproducibility

## What can be re-run today, without any licence

| Command | Runs | Needs |
|---|---|---|
| `python -m pytest` | 123 tests: legacy-code characterisation, revised helpers, TraCI controllers, data integrity, SUMO and TraCI smoke tests | Python 3.10+, pandas; SUMO optional |
| `python analysis/replay_legacy_controller.py` | Unmodified legacy `main()` against a fake VISSIM | nothing else |
| `python sumo/run_scenarios.py` | All recovered SUMO packages | `pip install eclipse-sumo` |
| `python sumo/traci/run_traci_experiment.py` | Replicated TraCI controller experiment (160 runs) | `eclipse-sumo`, `libsumo`, `scipy` |
| `python analysis/make_figures.py` | Every figure in `figures/` | the CSVs in `data/` |
| `python analysis/audit_exports.py` / `audit_inpx.py` | Regenerates `data/derived/` from raw exports | the **private** archives (see `data/raw/README.md`) |

## What cannot be re-run

* The VISSIM simulations: no licence is available to this project. The models themselves are published in
  `vissim/models/`, so anyone with PTV VISSIM 2025 can re-run them.
* The original analysis that produced the reported delay and emission values: the script is lost.

## Limitations of the original study (as now understood)

1. One simulation per controller and scenario; no replication across seeds.
2. Controller input is an evaluation-interval queue result, not an instantaneous measurement.
3. The split is confined to 67–80 s, while the fixed-time baseline gives NS 87–93 s.
4. Calibration was visual and literature-based; no field validation of delay or queues.
5. Demand (8,520 veh/h) leaves 3,900–5,900 vehicles unable to enter by 4,200 s, so per-vehicle delay
   describes only vehicles that got in.
6. Some runs (Base later batch, Monsoon, Night) were most likely made on a model copy without signal
   heads, so they are effectively unsignalised and unusable as fixed-time or adaptive results.
7. No intergreen/all-red clearance in either controller.

## Limitations of this repository's analysis

* Identifying the analysed runs relies on matching printed figures to exported series. The match is exact
  for the time series, but the reported bar-chart values remain unexplained.
* Effective fixed-time greens carry a ±3 s ambiguity from amber placement.
* SUMO runs use one seed each and an uncalibrated model.

## Checklist: missing items that would strengthen reproducibility

- [ ] Original analysis notebook or script that computed 30.77 / 28.92 / 34.77 / 33.62 s/veh
- [ ] Record confirming the signal-head `.inpx` and the intended `SIMULATION_NO` were used for runs 2, 3, 4 and 8
- [ ] VISSIM `.err` / `.att` files or signal-times tables showing the controller actually switched signals
- [ ] Field counts and turning proportions used to set the 8,520 veh/h inputs
- [x] Supervisor's agreement to publish the `.inpx` models (published in `vissim/models/`)
- [ ] A licensed re-run: seed increment > 0, ≥ 10 seeds per arm, paired analysis with confidence intervals
- [x] A SUMO TraCI port of the controller with replicated seeds ([traci_experiment.md](traci_experiment.md))
- [ ] Calibrating the SUMO network against the VISSIM fixed-time baseline and field data
