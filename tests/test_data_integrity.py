"""Checks on the published data tables (reported values and derived audit tables)."""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
REP = pd.read_csv(ROOT / "data" / "reported" / "reported_results.csv")
DER = ROOT / "data" / "derived"


def reported(q, sc, ctl):
    return float(REP[(REP.quantity == q) & (REP.scenario == sc) & (REP.controller == ctl)].value.iloc[0])


@pytest.mark.parametrize("sc,pct", [("Base", 6.01), ("Encroach", 3.31)])
def test_reported_percentages_follow_from_reported_means(sc, pct):
    f, a = reported("mean_delay", sc, "fixed"), reported("mean_delay", sc, "adaptive")
    assert round(100 * (f - a) / f, 2) == pct


def test_no_reported_value_claims_reproduction():
    assert not (REP.reproduced_from_recovered_exports == "yes").any()


def test_derived_tables_exist():
    for name in ("distinct_simulations.csv", "comparisons.csv", "run_identity.csv",
                 "interval_network_delay.csv", "inpx_settings.csv", "legacy_replay.csv",
                 "sumo_runs.csv", "raw_manifest.csv", "traci_runs.csv", "traci_paired.csv"):
        assert (DER / name).exists(), name


def test_monsoon_night_and_base_batch_flagged_identical():
    c = pd.read_csv(DER / "comparisons.csv")
    flags = c.groupby(["scenario", "fixed_simrun", "adaptive_simrun"]).outputs_identical.first()
    assert flags[("Monsoon", 10, 21)] and flags[("Night", 1, 11)] and flags[("Base", 10, 19)]
    assert not flags[("Base", 3, 8)] and not flags[("Encroach", 2, 4)]


def test_every_condition_has_at_most_three_distinct_outputs():
    ident = pd.read_csv(DER / "run_identity.csv")
    vn = ident[ident.export == "vehicle_network"]
    assert vn.groupby("scenario").distinct_output.nunique().max() <= 3


def test_two_output_regimes_at_full_demand():
    """Runs where fixed == adaptive deliver far more vehicles than runs where the controller matters.

    Supports the inference (docs/evidence_audit.md section 6) that the identical runs were made on a
    model copy without signal heads.
    """
    d = pd.read_csv(DER / "distinct_simulations.csv")
    d = d[d.scenario != "Night"]  # different demand level
    ident = pd.read_csv(DER / "run_identity.csv")
    vn = ident[ident.export == "vehicle_network"]
    shared = set(vn[vn.controller == "fixed"].distinct_output) & set(vn[vn.controller == "adaptive"].distinct_output)
    first_run = d.member_simruns.str.split().str[0].astype(int)
    labels = {(r.scenario, r.simrun): r.distinct_output for r in vn.itertuples()}
    d = d.assign(label=[labels[(sc, run)] for sc, run in zip(d.scenario, first_run)])
    regime_a = d[d.label.isin(shared)]
    regime_b = d[~d.label.isin(shared)]
    assert set(regime_a.scenario) == {"Base", "Monsoon"}
    assert regime_a.net_vehicles_arrived.min() > 4800
    assert regime_b.net_vehicles_arrived.max() < 3700


def test_traci_experiment_is_complete_and_paired():
    runs = pd.read_csv(DER / "traci_runs.csv")
    assert runs.groupby(["scenario", "controller"]).seed.nunique().eq(20).all()
    assert len(runs) == 160 and runs.share_completed.eq(1.0).all()
    paired = pd.read_csv(DER / "traci_paired.csv")
    assert paired.n_seeds.eq(20).all()
