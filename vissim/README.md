# VISSIM workstream

## `legacy/original_legacy_controller.py`

The queue-adaptive controller exactly as it survives: 9,071 bytes, SHA-256 in
[`legacy/SHA256SUMS`](legacy/SHA256SUMS), byte-identical to `ug final final.py` in both recovered result
archives. **Do not edit it.** It has Windows (CRLF) line endings, which `.gitattributes` asks git to preserve. If git converts them anyway, the check still passes: it accepts the archived bytes or the same file with only line endings converted, and fails on any other change. Corrections live in
[`src/lanka_signal/revised_logic.py`](../src/lanka_signal/revised_logic.py), and the differences are
documented in [`docs/legacy_code_audit.md`](../docs/legacy_code_audit.md).

To run it as originally intended you need Windows, a licensed PTV VISSIM 2025 with COM, `pywin32`, and
the original `.inpx`. None of these is available to this project now. The machine-specific
`INPX_PATH` and the hard-coded `SIMULATION_NO = 20` would also have to be changed.

Without VISSIM, the file can be exercised in two ways:

```bash
python -m pytest tests/test_legacy_logic.py         # characterisation tests
python analysis/replay_legacy_controller.py          # replay main() on a fake COM layer
```

## Model (not included)

Five `.inpx` scenario models exist in two archived versions. Their extracted settings, not their geometry,
are published in [`data/derived/inpx_settings.csv`](../data/derived/inpx_settings.csv):

| Setting | Value |
|---|---|
| VISSIM | 2025.00-11 and 2025.00-06 (two archived builds) |
| Simulation | 4,500 s; 10 steps/s (Lane_Block 15); seed 42, `numRuns = 1` |
| Evaluation | 600–4,200 s, 60 s intervals (queues: one interval) |
| Signal control | `FIXEDTIME`, 153 s; SG1 = East–West, SG2 = North–South; amber 3 s; intergreen 0 s |
| Queue counters | 1 N (link 2), 2 E (link 4), 3 S (link 6), 4 W (link 8) |
| Signal heads | 8 (2 lanes × 4 approaches) in the intended models (`ug_results.zip`, confirmed by the author); a second archived copy of Base, Lane_Block, Monsoon and Night has **0** |
