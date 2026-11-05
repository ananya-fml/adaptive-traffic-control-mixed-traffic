Lanka Phase 5C: Base + Encroachment SUMO scenario files

Files:
1. lanka_base_stable.rou.xml
   - Treat this as the BASE SUMO scenario.
   - Uses stable reduced flows and safer lane-changing parameters.

2. lanka_encroachment.rou.xml
   - Encroachment scenario.
   - Uses the same reduced demand base.
   - Adds intermittent kerbside stopping/blocking vehicles on inbound approach lanes:
     v2_0, v6_0, v4_0, v8_0.
   - Slightly reduces speeds and increases gaps for disturbed roadside-friction behaviour.

3. lanka_base_stable.sumocfg
4. lanka_encroachment.sumocfg

Important:
- These .sumocfg files assume your net/add files are named:
  lanka_phase5c.net.xml
  lanka_phase5c.add.xml
- Put these files in the same folder as your net/add files.
- If kerbside obstruction appears on the wrong side in GUI, open lanka_encroachment.rou.xml
  and change blocker stop lanes from _0 to _1, for example v2_0 -> v2_1.

Run:
sumo-gui -c lanka_base_stable.sumocfg
sumo-gui -c lanka_encroachment.sumocfg

If encroachment causes too much blockage:
- reduce blocker duration from 900 to 300-450 seconds
- or remove one blocker per north/south approach.

If encroachment is not visible enough:
- increase duration to 1200 seconds
- add one more auto blocker on the affected approach.
