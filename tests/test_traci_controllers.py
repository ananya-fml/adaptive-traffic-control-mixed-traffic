"""Unit tests for the TraCI-experiment controllers (no SUMO needed)."""
import itertools

import pytest

from lanka_signal import legacy_logic as L
from lanka_signal.traci_controllers import FixedTime, QueueProportional, legacy_split, make_controller


@pytest.mark.parametrize("ns,ew", list(itertools.product([0, 0.5, 3, 7.5, 20, 60, 140], repeat=2)))
def test_legacy_split_equals_archived_proportional_split(ns, ew):
    archived = L.proportional_split({"NS": ns, "EW": ew})
    ported = legacy_split({"NS": ns, "EW": ew}, cycle=153, amber=3, all_red=0, g_min=10, g_max=80)
    assert ported == pytest.approx(archived)


def run(ctrl, queues_fn, seconds):
    return [ctrl.step(t, queues_fn(t)) for t in range(seconds)]


def durations(states, stage, symbol):
    out, n = [], 0
    for s in states:
        if s[stage] == symbol:
            n += 1
        elif n:
            out.append(n)
            n = 0
    return out


def test_fixed_96_matches_archived_phase5c_programme():
    st = run(make_controller("fixed_96"), lambda t: None, 96 * 3)
    assert durations(st, "EW", "G")[:2] == [40, 40]
    assert durations(st, "NS", "G")[:2] == [50, 50]
    assert durations(st, "EW", "y")[:2] == [3, 3]
    assert not any(s["EW"] == "G" and s["NS"] in "Gy" for s in st)
    assert not any(s["NS"] == "G" and s["EW"] in "Gy" for s in st)


def test_fixed_153_cycle():
    assert FixedTime(ew_green=60, ns_green=87).cycle == 153


def test_adaptive_balanced_queues_below_threshold():
    c = QueueProportional(cycle=153)
    st = run(c, lambda t: {"NS": 3.0, "EW": 3.0}, 2000)
    # first cycle starts from EMA 0.5*3 per stage -> 73.5 s targets -> 74 s served in whole seconds
    assert set(durations(st, "NS", "G")[:-1]) == {74}
    assert set(durations(st, "EW", "G")[:-1]) == {74}


def test_adaptive_extends_to_max_when_queue_stays_long():
    c = QueueProportional(cycle=153)
    st = run(c, lambda t: {"NS": 50.0, "EW": 50.0}, 2000)
    assert set(durations(st, "NS", "G")[:-1]) == {80}


def test_adaptive_heavier_stage_gets_cap():
    c = QueueProportional(cycle=153)
    st = run(c, lambda t: {"NS": 5.0, "EW": 0.5}, 2000)  # both below 6 m tail threshold
    assert set(durations(st, "NS", "G")[1:-1]) == {80}
    assert set(durations(st, "EW", "G")[1:-1]) == {67}


def test_adaptive_never_conflicting_greens_and_amber_is_3s():
    c = QueueProportional(cycle=96)
    st = run(c, lambda t: {"NS": (t % 37), "EW": (t % 23)}, 3000)
    assert not any(s["NS"] == "G" and s["EW"] != "r" for s in st)
    assert not any(s["EW"] == "G" and s["NS"] != "r" for s in st)
    assert set(durations(st, "NS", "y")[:-1]) == {3}


def test_unknown_controller_rejected():
    with pytest.raises(ValueError):
        make_controller("max_pressure")
