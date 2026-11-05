# SUMO workstream (exploratory)

Recovered SUMO packages from the VISSIM → SUMO migration, kept **unmodified**. The original READMEs
are kept as `ORIGINAL_README*.txt`.

| Folder | Contents | Runs? |
|---|---|---|
| `ug_phase5_fixed3/` | Package delivered for the UG report: plain-XML network, compiled `.net.xml`, 92 flows (8,520 veh/h), 8 vTypes, 4 static signals (153 s), 8 E2 detectors | Yes; gridlocks (35 % of vehicles enter) |
| `phase5c/` | Phase 5C "exit-fix" network (enlarged ring, wider exits, 96 s signals), full / reduced routes, plus later `base` and `encroachment` scenarios | Base and encroachment run freely at about 31 % of VISSIM demand; the default `.sumocfg` fails (see below) |

## Run

```bash
pip install eclipse-sumo            # SUMO 1.28.0 tested
python sumo/run_scenarios.py        # builds nets with netconvert in a temp dir, runs everything
python sumo/run_scenarios.py --quick
```

Or by hand:

```bash
cd sumo/phase5c
netconvert --node-files lanka_phase5c.nod.xml --edge-files lanka_phase5c.edg.xml \
           --connection-files lanka_phase5c.con.xml -o lanka_phase5c.net.xml
sumo-gui -c lanka_base_stable.sumocfg
```

`lanka_phase5c.sumocfg` contains `<ignore-junction-blocker value="true"/>`, which SUMO rejects as a
non-number. The runner reproduces that config with `--ignore-junction-blocker 5` on the command line
(the value the later configs use) and leaves the file untouched.

Results and interpretation: [`docs/sumo_migration.md`](../docs/sumo_migration.md). These runs use the static signal programmes.
The adaptive TraCI experiment added in November 2026 is in [`traci/`](traci).
