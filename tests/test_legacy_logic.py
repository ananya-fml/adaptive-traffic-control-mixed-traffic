"""Characterisation tests for the UNMODIFIED legacy controller.

These tests pin down what the archived code does, including its defects, so the
audit in docs/legacy_code_audit.md is executable. They do not validate the
controller's traffic performance (no traffic is simulated).
"""
import math

import pytest

from lanka_signal import legacy_logic as L
from lanka_signal.fake_vissim import green_intervals, replay_legacy_main


def test_legacy_file_matches_archive():
    # "exact" = archived bytes; "line-endings-only" = git converted CRLF to LF, code unchanged
    assert L.verify_legacy() in {"exact", "line-endings-only"}


def test_any_code_change_is_detected(tmp_path):
    import pytest as _pytest
    data = L.LEGACY_PATH.read_bytes().replace(b"= 80.0", b"= 90.0", 1)
    f = tmp_path / "x.py"
    f.write_bytes(data)
    with _pytest.raises(RuntimeError):
        L.verify_legacy(f)


def test_lf_converted_copy_is_accepted(tmp_path):
    f = tmp_path / "x.py"
    f.write_bytes(L.LEGACY_PATH.read_bytes().replace(b"\r\n", b"\n"))
    assert L.verify_legacy(f) == "line-endings-only"


def test_legacy_parameters_match_handoff_table():
    p = L.PARAMETERS
    assert (p["CYCLE_LEN"], p["AMBER"], p["ALL_RED"]) == (153.0, 3.0, 0.0)
    assert (p["MIN_GREEN"], p["MAX_GREEN"]) == (10.0, 80.0)
    assert (p["TARGET_TOTAL_SEC"], p["WARMUP_SEC"], p["COOLDOWN_SEC"]) == (4500.0, 600.0, 300.0)
    assert (p["SIMULATION_NO"], p["TIME_INTERVAL"], p["RAND_SEED"]) == (20, 1, 42)
    assert L.STAGES == [{"name": "NS", "sg_ids": [2], "qc_ids": [1, 3]},
                        {"name": "EW", "sg_ids": [1], "qc_ids": [2, 4]}]


@pytest.mark.parametrize("share", [i / 20 for i in range(21)])
def test_split_always_uses_full_budget_and_stays_in_67_80(share):
    g = L.proportional_split({"NS": share, "EW": 1 - share})
    assert math.isclose(sum(g.values()), 147.0)
    assert all(67.0 - 1e-9 <= v <= 80.0 + 1e-9 for v in g.values())


def test_split_is_proportional_only_between_45_and_55_percent():
    assert L.proportional_split({"NS": 0.44, "EW": 0.56}) == {"NS": 67.0, "EW": 80.0}
    g = L.proportional_split({"NS": 0.5, "EW": 0.5})
    assert g == {"NS": 73.5, "EW": 73.5}


def test_zero_queues_collapse_cycle_to_minimum_greens():
    assert L.proportional_split({"NS": 0.0, "EW": 0.0}) == {"NS": 10.0, "EW": 10.0}


def test_cycle_plan_leaves_81s_remainder():
    assert L.compute_cycle_plan(3600.0) == (23, 81.0)


def test_read_queue_returns_none_for_missing_value():
    class QC:
        def AttValue(self, _):
            return None
    class Sim:
        SimulationSecond = 700.0

    class V:
        Simulation = Sim

    assert L.read_queue_m(QC(), V) is None


def test_replay_none_queue_crashes():
    with pytest.raises(TypeError):
        replay_legacy_main(lambda qc, t, a: None)


def test_replay_reads_fixed_run_and_interval_index():
    fake = replay_legacy_main(lambda qc, t, a: 3.0)
    assert {r[2] for r in fake.qlen_reads} == {"QLen(20,1)"}


def test_replay_constant_queue_above_threshold_extends_to_max_green():
    fake = replay_legacy_main(lambda qc, t, a: 12.0)
    ew = [b - a for a, b in green_intervals(fake.sig_log, 1)]
    ns = [b - a for a, b in green_intervals(fake.sig_log, 2)]
    assert set(map(round, ew)) == {80} and set(map(round, ns)) == {80}
    # 23 cycles of 166 s instead of 153 s: the script runs ~299 s past SimPeriod
    assert fake.clock.second == pytest.approx(4799.1)


def test_replay_balanced_small_queue_rounds_green_up_by_stepping():
    fake = replay_legacy_main(lambda qc, t, a: 3.0)
    ew = [b - a for a, b in green_intervals(fake.sig_log, 1)]
    assert set(map(round, ew)) == {74}  # 73.5 s target served in whole 1 s steps


def test_replay_zero_queue_ends_run_early():
    fake = replay_legacy_main(lambda qc, t, a: 0.0)
    assert fake.clock.second == pytest.approx(1579.1)
    assert fake.Simulation.stopped_at == pytest.approx(1579.1)


def test_no_all_red_between_conflicting_greens():
    fake = replay_legacy_main(lambda qc, t, a: 3.0)
    ends = [b for _, b in green_intervals(fake.sig_log, 1)]
    ns_starts = [a for a, _ in green_intervals(fake.sig_log, 2)]
    # NS green starts exactly when EW amber ends (amber 3 s, ALL_RED = 0)
    assert any(math.isclose(s - e, 3.0, abs_tol=1e-6) for e in ends for s in ns_starts)
