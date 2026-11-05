"""Smoke test: the Phase 5C 'base' SUMO scenario builds and runs (skipped without SUMO)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def have_sumo():
    try:
        import sumo  # noqa: F401
        return True
    except ImportError:
        return shutil.which("sumo") is not None


@pytest.mark.skipif(not have_sumo(), reason="SUMO not installed (pip install eclipse-sumo)")
def test_phase5c_base_runs():
    out = subprocess.run([sys.executable, str(ROOT / "sumo" / "run_scenarios.py"), "--quick"],
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    assert "'exit_code': 0" in out.stdout
