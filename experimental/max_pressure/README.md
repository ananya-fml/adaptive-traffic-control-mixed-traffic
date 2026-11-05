# Experimental: three-controller VISSIM comparison framework (UNVALIDATED)

> **Status: never executed in VISSIM. Produced no results.**
> Illustrative configuration; not used to obtain any number reported anywhere in this repository.

This folder holds a 2026 prototype (`experiment.py`) for a matched-seed VISSIM comparison of
(1) fixed-time, (2) a revised queue-proportional controller and (3) a movement-based
Max-Pressure controller. It was written after the original project, without VISSIM access,
as a design for a *future* experiment.

| Item | Status |
|---|---|
| Python syntax and pure functions | `python test_logic.py` passes (2 tests) |
| VISSIM COM compatibility | **Untested** |
| Link IDs `101–104` / `201–204` in `config.json` | **Placeholders**, not Lanka model IDs |
| Fixed-time split `72/73 s` | **Placeholder**. The archived model's programme is EW ≈ 60–63 s, NS ≈ 87–93 s ([docs/legacy_code_audit.md](../../docs/legacy_code_audit.md#4-fixed-time-reference-programme)) |
| `all_red_sec = 1` | Differs from the archived model (0 s) |
| Seeds `11…110` | Placeholders. Note the archived model used one seed (42) for every run |
| Queue sensing | New stopped-vehicle sensing from `Link.Vehs`; **not** the legacy `QLen` read |
| Outputs | Sampled proxies only, not VISSIM delay, stops or emissions |

The Max-Pressure term is a finite-sensing-zone approximation,
`P_s = Σ s_ij · r_ij · (Q_up,i − Q_down,j)`. Classical throughput-optimality results
assume conditions (point queues, known saturation flows, adequate storage) that are not
established for the short, shared, mixed-traffic links at Lanka.

## What would make it a real experiment

1. Licensed VISSIM with COM access, and the intended `.inpx` models with signal heads
   (an alternative archived copy of four models has none; see [docs/evidence_audit.md](../../docs/evidence_audit.md#6-model-versions-signal-heads)).
2. The true approach and exit link IDs, turning fractions and saturation flows.
3. A random-seed increment, so that replications differ, and at least 10–20 seeds per controller.
4. Paired analysis of VISSIM's own Node Results and Vehicle Network Performance, including
   latent demand.

A licence-free route now exists: the queue-proportional controller has been ported to SUMO/TraCI
([docs/traci_experiment.md](../../docs/traci_experiment.md)). A Max-Pressure controller could be added
to the same harness; its results would be **new SUMO results**, not a re-run of the VISSIM study.

`PROTOTYPE_NOTES.md` is the prototype's original README, kept verbatim.
