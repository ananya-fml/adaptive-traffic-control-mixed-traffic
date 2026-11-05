# Reconciliation: report text vs code vs recovered evidence

Statements from the UG report (Nov 2025) and the thesis (Apr 2026), checked against the legacy code,
the model files and the exports. "Both" means the statement appears in both documents.

| # | Statement in the reports | What the evidence shows | Status |
|---|---|---|---|
| 1 | Delay 30.77 → 28.92 s/veh (Base, −6.0 %), 34.77 → 33.62 s/veh (Encroach, −3.3 %), from node results (both) | Not regenerable from the exports; report-pair node and network delay changes are between −1.5 % and +1.5 % ([evidence §4–5](evidence_audit.md#4-attempts-to-reproduce-the-headline-delays)) | **Not reproduced** |
| 2 | CO/NOx/VOC/fuel −1.8–1.9 % (Base), −1.5 % (Encroach) (both) | Node emissions per vehicle in the report pairs: −3.1 % (Base), −2.1 % (Encroach). In every exported row CO, NOx, VOC and fuel change by exactly the same percentage, so the node emission columns are fixed multiples of fuel consumption: one quantity, not four. Summary table says "CO₂"; text and charts say CO. Units never stated | **Not reproduced**; labelling inconsistent |
| 3 | "Random seeds: up to 5 … results averaged" (both) | Each condition has 1–2 distinct simulations; repeated runs reuse seed 42 | **Contradicted** |
| 4 | "Queue length retrieved every simulation second" (both) | Queue read once per cycle for the split and once per second only inside a green for the extension, always from `QLen(20,1)`, a single-interval evaluation result | **Inaccurate** |
| 5 | "Decision checks … once per cycle (every ~60 s)" (both) | Cycle is nominally 153 s | **Inconsistent** |
| 6 | "Extend 1–2 s if queue > threshold; terminate early if below" and flowchart (both) | Code: proportional split each cycle, heaviest stage first, 1 s extensions after the planned green; no early termination | **Code differs**; the abstract's "proportional green allocation" matches the code |
| 7 | COM call `SignalController.SetAttValue("STATE", …)` (both) | Code writes `SigState` on individual signal groups | **Code differs** |
| 8 | `QueueCounter.AttValue("QLen(11,1)")` (both) | Code reads `QLen(20,1)`; header comment says 11 | **Code version differs from figure** |
| 9 | "Intergreen times set per IRC guidelines" (both) | Model intergreen matrix 0 s; code `ALL_RED = 0` | **Inconsistent** |
| 10 | Optimised fixed-time 153 s plan via Webster's method (both) | 153 s programme confirmed: EW ≈ 60–63 s, NS ≈ 87–93 s green. Webster inputs not preserved; back-calculation gives Y ≈ 0.91 ([methods](methodology.md#how-it-was-set-websters-method)) | Cycle **confirmed**; inputs not recorded |
| 11 | Vehicle classes: 5 (methods) vs 8 (abstract, SUMO section) (thesis) | Not checked (model geometry and types not extracted) | Internal inconsistency |
| 12 | "Two scenarios were created", then five defined (thesis) | Five models exist | Wording error |
| 13 | Adaptive "consistently outperformed … benefits particularly significant under encroachment and lane-block" (thesis conclusion) | Reports' own numbers show a smaller gain under encroachment (3.3 % vs 6.0 %); no lane-block number is reported; exports show mixed signs | **Overclaim** |
| 14 | "Both scenarios used identical traffic volumes" (UG) | Base and Encroach inputs are both 8,520 veh/h | **Confirmed** |
| 15 | Simulation 4,500 s, warm-up 600 s, evaluation 600–4,200 s, 10 steps/s (both) | Confirmed in all models, except Lane_Block at 15 steps/s | **Confirmed** (one exception) |
| 16 | Early trial ≈ 21 % reduction, superseded (both) | Earlier runs not in the archive | Correctly labelled as non-final |
| 17 | SUMO "operational validation against VISSIM outputs" (thesis framework step 11) | Validation was visual/qualitative; no quantitative comparison file exists | **Overstated** |
| 18 | SUMO calibration table (thesis) | Matches no recovered route file exactly; motorbike and auto rows match Phase 5C *full* ([sumo_migration §4](sumo_migration.md#4-vehicle-type-parameters-thesis-table-vs-files)) | **Partially matched** |
| 19 | SUMO signal plan "preserved … cycle structure" (153 s) (thesis) | UG package uses 153 s (60+3 / 87+3); Phase 5C uses **96 s** (40+3 / 50+3) | **True only for the UG package** |

The reported figures themselves (time series, headway and speed histograms) are consistent with the
exports for the identified run pairs. The discrepancy lies in the bar-chart and summary values, not in the
time-series plots.
