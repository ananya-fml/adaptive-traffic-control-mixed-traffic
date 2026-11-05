"""Load the historical controller source exactly as archived.

The archived file imports ``win32com.client`` at module level, which only exists
on Windows with pywin32. We register a stand-in module under that name *before*
importing, so the legacy source is executed byte-for-byte unchanged. The SHA-256
of the file is verified on every load.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_PATH = REPO_ROOT / "vissim" / "legacy" / "original_legacy_controller.py"
LEGACY_SHA256 = "a96a0dcea97e882ac83439d9313a21ae78cab2a51a0e6faf6fe725f419890a96"   # archived bytes (CRLF)
# Same file with CRLF converted to LF, as git may store it on some systems. Code content is identical.
LEGACY_SHA256_LF = "973c098720d81ad729fa2c03d8924336e704b692d3659e474c89302f7e5e03c6"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_legacy(path: Path = LEGACY_PATH) -> str:
    """Return "exact" or "line-endings-only"; raise if the code differs from the archive."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == LEGACY_SHA256:
        return "exact"
    if hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == LEGACY_SHA256_LF:
        return "line-endings-only"
    raise RuntimeError(
        f"Legacy controller content differs from the archived file ({_sha256(path)}); it was modified."
    )


def load_legacy(dispatch=None, module_name: str = "lanka_legacy_controller"):
    """Import the legacy controller module.

    Parameters
    ----------
    dispatch:
        Callable used as ``win32com.client.Dispatch``. Pass a factory returning a
        :class:`lanka_signal.fake_vissim.FakeVissim` to replay ``main()``.
        If omitted, calling ``Dispatch`` raises, so only the pure helpers are usable.
    """
    verify_legacy()

    def _no_vissim(*_a, **_k):
        raise RuntimeError("No VISSIM available: supply a fake dispatch to replay main().")

    client = types.ModuleType("win32com.client")
    client.Dispatch = dispatch or _no_vissim
    pkg = types.ModuleType("win32com")
    pkg.client = client
    saved = {k: sys.modules.get(k) for k in ("win32com", "win32com.client")}
    sys.modules["win32com"] = pkg
    sys.modules["win32com.client"] = client
    try:
        spec = importlib.util.spec_from_file_location(module_name, LEGACY_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return module


# Convenience accessors for the pure helpers (no COM involved).
_legacy = load_legacy()
proportional_split = _legacy.proportional_split
compute_cycle_plan = _legacy.compute_cycle_plan
read_queue_m = _legacy.read_queue_m
PARAMETERS = {
    name: getattr(_legacy, name)
    for name in (
        "SIGNAL_CONTROLLER_ID", "TARGET_TOTAL_SEC", "WARMUP_SEC", "COOLDOWN_SEC",
        "CYCLE_LEN", "AMBER", "ALL_RED", "MIN_GREEN", "MAX_GREEN", "SIM_RES",
        "STEP_SEC", "RAND_SEED", "SIMULATION_NO", "TIME_INTERVAL", "EMA_ALPHA",
        "TAIL_CLEAR_M",
    )
}
STAGES = _legacy.STAGES
