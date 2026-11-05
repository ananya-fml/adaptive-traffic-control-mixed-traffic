This package fixes the connection topology.

Why fixed2 failed
-----------------
Connections like v34a -> v27 were invalid because the source edge ended at one node
while the destination edge began at a different node. SUMO only allows connections
at shared junction nodes.

What fixed3 changes
-------------------
- entry links connect to the ring edge that starts at the same node
- exit links are attached at the correct downstream shared node
- route definitions were updated so every path uses only valid node-to-node transitions

Build:
  netconvert --node-files lanka_phase5_fixed3.nod.xml --edge-files lanka_phase5_fixed3.edg.xml --connection-files lanka_phase5_fixed3.con.xml -o lanka_phase5_fixed3.net.xml

Run:
  sumo-gui -c lanka_phase5_fixed3.sumocfg
