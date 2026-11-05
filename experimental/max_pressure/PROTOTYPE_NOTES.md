# Lanka VISSIM: three-controller matched-seed comparison

This experiment implements **(1) a fixed-time signal**, **(2) a queue-length-proportional adaptive split**, and **(3) a movement-based max-pressure controller** for a two-stage NS/EW intersection. It uses 4,500 seconds total, 600–4,200 seconds for analysis (3,600 seconds), SimRes 10 and ten paired random seeds by default.

**Important:** This is a complete experiment *framework*, not a pre-calibrated plug-and-play reproduction of your original network. Your original Python file gave signal group IDs (NS=2, EW=1), but did **not** establish approach/exit **link IDs, actual turning proportions, calibrated saturation rates, or the actual optimized fixed-time green split**. The 101–104/201–204 link IDs are **illustrative placeholders** and the 72/73 s green split is an **illustrative 153 s cycle baseline**, **not your verified optimized plan**. Replace those details before running or interpreting results.

## Installation and run

1. Use **Windows** with licensed **PTV VISSIM 2025/2026, with COM access**, and install Python for the same architecture as VISSIM. `pip install pywin32`.
2. In `config.json`, set `network_inpx` and `scenarios[].network_inpx` to existing `.inpx` model paths. You may add `encroached`, `night`, `monsoon`, and `lane_block` scenarios, but each must point to a *separately configured, validated* VISSIM network with the **same movement/link mapping**. If each network uses different link IDs, run one scenario at a time with its own `config.json`.
3. Set `stages[].upstream_links` from VISSIM's **Links** list. These must be the *last actual inbound links before the intersection/connector*, with geometry oriented toward the stop line. If the final inbound link ends past the stop line or queues span several links, modify the sensing logic or sensor mapping. Keep the signal groups consistent with the controlling signal heads.
4. Set `movements[]`: **every allowed turn from every upstream link** should have a downstream exit link, a calibrated turning fraction, and a saturation discharge rate (vehicles/s). For every upstream link, fractions must sum to one (±0.02). If a link feeds shared movements, use multiple movement rows. **Do not leave the default one-to-one movement mapping as scientific data.**
5. Confirm the **downstream links** are actual outgoing receiving links. They should be long enough to observe congestion within `queue_downstream_window_m`; consider storing maximum available downstream capacity or detecting stop-line blockage if the physical exit link is short.
6. Replace `fixed_greens_sec` with your **actual optimized fixed-time stage greens** (integer seconds summing to 145 seconds for a 153-second cycle with 3 s amber and 1 s all-red per stage). Check your actual intergreens and required signal safety rules; the hardcoded amber/all-red must be approved for your geometry. If your fixed-time program has different clearance requirements, adjust the model and implementation accordingly.
7. Ensure **signal groups' `SigState` is writable during simulation** for your controller setup and license. VISSIM has signal controller types and external signal control considerations. Test one seed with an empty copy of your network before a full batch.
8. From the folder containing `experiment.py` and `config.json`, run: `python experiment.py --config config.json`.

## What the algorithms do

- **Fixed:** sequential NS/EW with a user-provided baseline split; 153 s only when stage green periods are whole seconds and sum to 145 s as configured.
- **Queue proportional:** instantaneous approximate *stopped-vehicle queue length in metres* on upstream links, EMA with alpha 0.5, bounded proportional allocation of two green splits each cycle. Both schemes follow stage order NS/EW, with mandatory amber/all-red.
- **Max-pressure:** `P(stage) = Σ_movements s_ij × r_ij × (Q_up,i − Q_down,j)`. Here `Q` is stopped-vehicle count within upstream/downstream observation windows, `r` is turn fraction and `s` is measured saturation flow (veh/s). Stage decisions made with min/max green, pressure hysteresis, and max opposing red (fairness). **This is a movement-weighted pressure approximation, NOT a theoretical guarantee of optimal network control**; standard Max-Pressure assumptions do not automatically apply to short, shared-lane VISSIM links or mixed traffic.

**Queue sensing:** `Link.Vehs.GetAll()` reads vehicles' `Pos` and `Speed` each simulated second. Stopped means speed ≤5 km/h. The upstream queue length approximation is the maximum separation from the link end among stopped vehicles in the observation window, summed across approach links. Vehicles stalled *before* the window are not measured; use a sufficiently long contiguous observation segment or enhance to multi-link queue sensing. **Units are not exactly VISSIM's QueueCounter QLen**. This fixes the old code's use of a fixed `QLen(simulation_no,time_interval)` evaluation index as if it were live.

## Outputs

Every scenario, method and seed produces a `*_trace.csv` (every 60 seconds by default). Also generated:

- `replicates.csv`: sampled mean upstream stopped count, summed queue length [m], max summed queue length [m], downstream stopped count, sampled stop onsets proxy, downstream-link entries proxy and signal changes.
- `summary.csv`: across-seed means and sample standard deviations.
- `paired_comparisons.csv`: within-seed percentage reductions vs fixed time for four measures (blank if baseline zero).

**This script does not automatically output scientifically defensible average vehicle delay, emissions or VISSIM's official throughput.** The sampled count of entries into downstream links is a rough observational proxy: it is not an official flow measurement. The sampled stop-onset count is likewise **not** VISSIM Stops. For delay/stop/emission conclusions, configure **Node Results, Delay Measurements, Data Collection, Vehicle Network Performance, and emissions evaluation** in VISSIM and compare exported official evaluations from the matching 600–4200 s interval, using consistent run IDs. For your publication, include confidence intervals or paired-seed variability and account for calibration and appropriate lane/sensor definitions.

## Limitations and preflight validation

- The script is syntax-checked but **has not been executed in a Windows VISSIM installation**. COM behavior and `SigState` editability must be checked on your local installation.
- `Link.Vehs.GetAll()` once per second can be slow on large networks. For a single junction it is usually practical; benchmark first.
- The start of simulation is all-red for one second, then the first green begins. All controllers share the same initialization rule, but fixed cycles are offset by that one second.
- Stage switches are made on 1 s policy boundaries with 0.1 s VISSIM time steps. A 153-second fixed cycle is exact after starting first green with integer green splits.
- Any planned comparison against *your original queue controller* should acknowledge that this new variant uses **different queue sensing** and does not implement the original gap-out tail-clear logic; it is a cleaner, like-for-like queue-proportional benchmark, not an exact source-code clone.
- For upstream links that serve multiple signals, shared lanes, protected turns, queue spillover onto earlier links, or heterogeneous service rates by movement, the stage/movement mapping may need an additional lane-level or route-aware sensor layer.
