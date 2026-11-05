"""Licence-free tooling for the Lanka adaptive-signal project.

Modules
-------
legacy_logic
    Loads the *unmodified* historical VISSIM-COM controller
    (``vissim/legacy/original_legacy_controller.py``) and exposes its functions.
    Nothing in the historical algorithm is re-implemented here.
fake_vissim
    A minimal stand-in for the VISSIM COM object model, so the historical
    ``main()`` can be replayed deterministically without PTV VISSIM. It replays
    *control logic only*; it simulates no vehicles.
revised_logic
    NEW code written in 2026 during the audit. Corrects defects found in the
    legacy helpers. It has never been run in VISSIM and produced no results.
"""

__all__ = ["legacy_logic", "fake_vissim", "revised_logic"]
