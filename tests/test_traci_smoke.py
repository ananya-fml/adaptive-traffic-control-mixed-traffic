"""Smoke test: one seed of every controller runs in SUMO via libsumo (skipped if unavailable)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("libsumo")
pytest.importorskip("scipy")


def test_traci_experiment_one_seed(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "sumo" / "traci" / "run_traci_experiment.py"),
                          "--seeds", "1", "--scenarios", "base", "--out-prefix", "traci_smoketest"],
                         capture_output=True, text=True, timeout=900)
    try:
        assert out.returncode == 0, out.stderr[-2000:]
        assert "4 runs" in out.stdout
    finally:
        for f in (ROOT / "data" / "derived").glob("traci_smoketest_*.csv"):
            f.unlink()
