"""The published VISSIM models are the intended (signal-head) versions, byte-identical to the archive."""
import hashlib
import re
from pathlib import Path

import pytest

MODELS = Path(__file__).resolve().parents[1] / "vissim" / "models"
SUMS = dict(reversed(line.split()) for line in (MODELS / "SHA256SUMS").read_text().splitlines() if line.strip())


@pytest.mark.parametrize("name", sorted(SUMS))
def test_model_checksum(name):
    assert hashlib.sha256((MODELS / name).read_bytes()).hexdigest() == SUMS[name]


@pytest.mark.parametrize("name", sorted(SUMS))
def test_model_has_eight_signal_heads(name):
    assert len(re.findall(r"<signalHead ", (MODELS / name).read_text(encoding="utf-8"))) == 8


def test_all_five_scenarios_present():
    assert len(SUMS) == 5
