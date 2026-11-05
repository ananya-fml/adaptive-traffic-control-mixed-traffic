Lanka Phase 5C - Exit-capacity / anti-gridlock patch

This keeps the Phase 5 VISSIM-like shape and applies the requested fixes:
- outer approach shapes kept the same
- only the inner ring is slightly enlarged
- exits / exit connectors made higher-capacity
- lane-changing aggressiveness increased
- blocking conservatism reduced
- shorter signal cycle
- reduced-demand default for a faster stable run
- full-demand file included for later evaluation

Build:
  netconvert --node-files lanka_phase5c.nod.xml --edge-files lanka_phase5c.edg.xml --connection-files lanka_phase5c.con.xml -o lanka_phase5c.net.xml

Run:
  sumo-gui -c lanka_phase5c.sumocfg
