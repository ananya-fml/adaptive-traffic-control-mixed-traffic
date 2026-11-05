# ===========================
# Adaptive Queue-Length Controller (Stage-Based)
# Runs total 4500 s with 600 s warm-up and 300 s cool-down
# Keeps SimRes=10 and reads queue via QLen(11,1)
# ===========================
# EDIT THESE: INPX/LAYX paths, controller ID, stage SG/QueueCounter IDs.
# Run on Windows with VISSIM + pywin32 installed.
# ===========================

import os
from collections import defaultdict

import win32com.client as com  # pip install pywin32

# ---------- USER CONFIG ----------
INPX_PATH = r"C:\Users\DELL\Desktop\Lanka_Original_Calibrated NC.inpx"
LAYX_PATH = r""  # optional, e.g., r"C:\path\to\your_layout.layx"


## The objects of the traffic signal control  
#scs=vnet.SignalControllers 
#sc=scs.ItemByKey(1)# sc = SignalController 1 
#sgs = sc.SGs # sgs=SignalGroups 
#sg_1 = sgs.ItemByKey(1)  # SignalGroup 1 
#sg_2 = sgs.ItemByKey(2)  # SignalGroup 2 
 
#dets = sc.Detectors  
#det_all = dets.GetAll() #All detectors are queried first 
#det_1 = det_all[0]    #The first detector of the detectors 
# Note that in Python tuple the 1st element is called by 0, although in Vissim GUI its number is 1! 

SIGNAL_CONTROLLER_ID = 1

# Define stages: each has signal groups (sg_ids) and queue counters (qc_ids).
# Replace IDs with your actual SG and QueueCounter IDs.
STAGES = [
    {"name": "NS", "sg_ids": [2], "qc_ids": [1, 3]},  # example
    {"name": "EW", "sg_ids": [1], "qc_ids": [2, 4]},  # example
]

# Timing policy
TARGET_TOTAL_SEC = 4500.0     # total simulation time
WARMUP_SEC       = 600.0      # warm-up at start (included in 4500)
COOLDOWN_SEC     = 300.0      # cool-down at end (included in 4500)
CYCLE_LEN        = 153.0      # adaptive "cycle" length for all stages together

# Intergreens and greens
AMBER            = 3.0        # amber per stage (s)
ALL_RED          = 0.0        # interstage all-red (s)
MIN_GREEN        = 10.0       # per stage min green (s)
MAX_GREEN        = 80.0      # per stage max green (s)

# Simulation stepping / randomness
SIM_RES          = 10         # steps/second (fixed to 10 as requested)
STEP_SEC         = 1.0        # controller check step inside green (seconds)
RAND_SEED        = 42

# Queue reading: use explicit indexed attribute as requested
SIMULATION_NO  = 20        #--------> first index in QLen(11,1) #change to the current sim no.
TIME_INTERVAL       = 1          # second index in QLen(11,1)

# EMA smoothing for queues (optional but useful to avoid jitter)
EMA_ALPHA        = 0.5        # 0..1, higher = more reactive
TAIL_CLEAR_M     = 6.0        # if residual queue > this, allow micro-extend

# ---------- HELPERS ----------
def set_sg_state(sg, state_code: int):
    """Set SG state: 1=RED, 3=GREEN, 4=AMBER."""
    sg.SetAttValue("SigState", state_code)

def run_for_seconds(Vissim, seconds: float):
    """Advance simulation 'seconds' in single steps (SimRes defines step granularity)."""
    target = Vissim.Simulation.SimulationSecond + seconds
    while Vissim.Simulation.SimulationSecond < target:
        Vissim.Simulation.RunSingleStep()

def read_queue_m(qc, Vissim):
    t = Vissim.Simulation.SimulationSecond
    #interval = int((t - 600) // 60) + 1

    #if interval < 1:
        #interval = 1
    #if interval > 60:
        #interval = 60

    v = qc.AttValue(f"QLen({SIMULATION_NO},{TIME_INTERVAL})")
    

    try:
        if v is not None:
            return float(v)
    except:
        return 0.0


def stage_queue_m(qc_objs, Vissim):
    """Sum queue (meters) across all queue counters for a stage."""
    return sum(read_queue_m(qc, Vissim) for qc in qc_objs)

def compute_cycle_plan(total_after_warmup: float):
    """How many full cycles + leftover remainder fit."""
    num_cycles = int(total_after_warmup // CYCLE_LEN)
    remainder  = total_after_warmup - num_cycles * CYCLE_LEN
    return num_cycles, remainder

def proportional_split(q_stage: dict):
    """
    Allocate stage greens proportionally to (smoothed) queue,
    honoring MIN/MAX and removing intergreens from the budget.
    """
    n = len(q_stage)
    usable = CYCLE_LEN - n * (AMBER + ALL_RED)
    if usable <= 0:
        return {k: MIN_GREEN for k in q_stage}

    base = {k: MIN_GREEN for k in q_stage}
    remaining = max(0.0, usable - n * MIN_GREEN)

    total_q = sum(max(q, 0.0) for q in q_stage.values())
    if total_q > 1e-9 and remaining > 0:
        for k, q in q_stage.items():
            w = max(q, 0.0) / total_q
            base[k] += remaining * w

    # cap and redistribute overflow
    capped = {k: min(v, MAX_GREEN) for k, v in base.items()}
    overflow = sum(base[k] - capped[k] for k in base if base[k] > MAX_GREEN)
    if overflow > 1e-6:
        headroom = {k: MAX_GREEN - capped[k] for k in capped}
        tot_head = sum(max(h, 0.0) for h in headroom.values())
        if tot_head > 1e-6:
            for k in capped:
                capped[k] += overflow * (max(headroom[k], 0.0) / tot_head)
    return capped

# ---------- MAIN ----------
def main():
    # Launch VISSIM and load network
    Vissim = com.Dispatch("Vissim.Vissim")
    if not os.path.isfile(INPX_PATH):
        raise FileNotFoundError(f"INPX not found: {INPX_PATH}")
    Vissim.LoadNet(INPX_PATH)
    if LAYX_PATH:
        if os.path.isfile(LAYX_PATH):
            Vissim.LoadLayout(LAYX_PATH)

    # Force engine settings BEFORE any stepping
    Vissim.Simulation.SetAttValue("SimBreakAt", 0)
    Vissim.Simulation.SetAttValue("SimPeriod", int(TARGET_TOTAL_SEC))  # end at 4500 s
    Vissim.Simulation.SetAttValue("RandSeed", int(RAND_SEED))
    Vissim.Simulation.SetAttValue("SimRes", int(SIM_RES))              # keep SimRes = 10

    # Objects
    sc = Vissim.Net.SignalControllers.ItemByKey(int(SIGNAL_CONTROLLER_ID))
    sgs = {st["name"]: [sc.SGs.ItemByKey(int(sgid)) for sgid in st["sg_ids"]] for st in STAGES}
    qcs = {st["name"]: [Vissim.Net.QueueCounters.ItemByKey(int(qid)) for qid in st["qc_ids"]] for st in STAGES}
    stage_names = [st["name"] for st in STAGES]

    # Warm-up
    print("Warm-up...")
    Vissim.Simulation.RunSingleStep()
    run_for_seconds(Vissim, WARMUP_SEC)

    # Plan cycles to fill (4500 - warm-up - cool-down)
    usable = max(0.0, TARGET_TOTAL_SEC - WARMUP_SEC - COOLDOWN_SEC)
    num_cycles, remainder = compute_cycle_plan(usable)
    print(f"Plan → Warm-up={WARMUP_SEC:.0f}s, Cycles={num_cycles}×{CYCLE_LEN:.0f}s, "
          f"Remainder={remainder:.1f}s, Cool-down={COOLDOWN_SEC:.0f}s, "
          f"Total={WARMUP_SEC + num_cycles*CYCLE_LEN + remainder + COOLDOWN_SEC:.1f}s")

    # EMA state
    q_ema = defaultdict(float)

    # Adaptive cycles
    for _ in range(num_cycles):
        # 1) Read and smooth queues per stage
        q_now = {name: stage_queue_m(qcs[name], Vissim) for name in stage_names}
        for name in stage_names:
            q_ema[name] = EMA_ALPHA * q_now[name] + (1.0 - EMA_ALPHA) * q_ema[name]

        # 2) Decide greens based on smoothed queues
        greens = proportional_split(q_ema)

        # 3) Order stages each cycle: heaviest queue first
        ordered_stages = sorted(stage_names, key=lambda n: q_ema[n], reverse=True)

        # 4) Serve stages in that order
        for k in ordered_stages:
            # all stages RED (interstage all-red)
            for others in sgs.values():
                for sg in others:
                    set_sg_state(sg, 1)  # RED
            if ALL_RED > 0:
                run_for_seconds(Vissim, ALL_RED)

            # current stage GREEN
            for sg in sgs[k]:
                set_sg_state(sg, 3)  # GREEN

            # serve green with simple gap-out style micro-extend
            served = 0.0
            target = greens[k]
            while served < target:
                run_for_seconds(Vissim, STEP_SEC)
                served += STEP_SEC

                # update current queue during the green
                curr_q = stage_queue_m(qcs[k], Vissim)

                # micro-extend if tail still present and under MAX
                if served >= target and curr_q > TAIL_CLEAR_M and target < MAX_GREEN:
                    target = min(MAX_GREEN, target + STEP_SEC)

            # AMBER for this stage
            for sg in sgs[k]:
                set_sg_state(sg, 4)  # AMBER
            if AMBER > 0:
                run_for_seconds(Vissim, AMBER)


    # Remainder to align exactly before cool-down (all-red remainder)
    if remainder > 0.0:
        for others in sgs.values():
            for sg in others:
                set_sg_state(sg, 1)  # RED
        run_for_seconds(Vissim, remainder)

    # Cool-down (all-red)
    for others in sgs.values():
        for sg in others:
            set_sg_state(sg, 1)  # RED
    run_for_seconds(Vissim, COOLDOWN_SEC)

    print("Done. Stopping simulation at 4500 s.")
    
    Vissim.Simulation.Stop()

if __name__ == "__main__":
    main()
