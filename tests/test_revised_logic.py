"""Tests for NEW (2026) helper code. Passing these says nothing about traffic performance."""
import math

import pytest

from lanka_signal.revised_logic import effective_green_range, proportional_split_revised


def test_effective_range_matches_legacy_behaviour():
    assert effective_green_range(153, 2, 3, 0, 10, 80) == (67, 80)


@pytest.mark.parametrize("ns,ew", [(0, 0), (1, 1), (5, 1), (1, 99), (0, 7), (40.2, 39.8)])
def test_budget_preserved_and_bounded(ns, ew):
    g = proportional_split_revised({"NS": ns, "EW": ew})
    assert math.isclose(sum(g.values()), 147.0)
    assert all(10 <= v <= 80 and float(v).is_integer() for v in g.values())


def test_zero_queues_split_equally_not_minimum():
    g = proportional_split_revised({"NS": 0, "EW": 0})
    assert sorted(g.values()) == [73.0, 74.0]


def test_missing_reading_is_an_error_not_none():
    with pytest.raises(ValueError):
        proportional_split_revised({"NS": None, "EW": 3.0})


def test_three_stage_overflow_is_redistributed_iteratively():
    g = proportional_split_revised({"A": 100, "B": 1, "C": 1}, cycle=153, amber=3, g_max=80)
    assert g["A"] == 80 and math.isclose(sum(g.values()), 144.0)
    assert all(v <= 80 for v in g.values())


def test_infeasible_budget_rejected():
    with pytest.raises(ValueError):
        proportional_split_revised({"NS": 1, "EW": 1}, cycle=200, g_max=80)
