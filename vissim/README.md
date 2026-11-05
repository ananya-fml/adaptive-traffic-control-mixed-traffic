# VISSIM workstream

## `legacy/original_legacy_controller.py`

The queue-adaptive controller exactly as it survives: 9,071 bytes, SHA-256 in
[`legacy/SHA256SUMS`](legacy/SHA256SUMS), byte-identical to `ug final final.py` in both recovered result
archives. **Do not edit it.** It has Windows (CRLF) line endings, which `.gitattributes` asks git to preserve. If git converts them anyway, the check still passes: it accepts the archived bytes or the same file with only line endings converted, and fails on any other change. Corrections live in
[`src/lanka_signal/revised_logic.py`](../src/lanka_signal/revised_logic.py), and the differences are
documented in [`docs/legacy_code_audit.md`](../docs/legacy_code_audit.md).

To run it as originally intended you need Windows, a licensed PTV VISSIM 2025 with COM, `pywin32`, and
the models in `models/`. A licence is not available to this project now. The machine-specific
`INPX_PATH` and the hard-coded `SIMULATION_NO = 20` would also have to be changed.

Without VISSIM, the file can be exercised in two ways:

```bash
python -m pytest tests/test_legacy_logic.py         # characterisation tests
python analysis/replay_legacy_controller.py          # replay main() on a fake COM layer
```

## Models (`models/`)

The five scenario models are included, in the versions the author confirmed as correct: the
signal-head versions from `ug_results.zip`, built in PTV VISSIM 2025.00-06. They are byte-identical to
the archive (checksums in [`models/SHA256SUMS`](models/SHA256SUMS)).

| File | Scenario |
|---|---|
| `lanka_original_calibrated.inpx` | Base |
| `Lanka_S1_Encroach.inpx` | Kerbside encroachment |
| `Lanka_S2_Lane_Block.inpx` | Lane blockage |
| `Lanka_S3_Monsoon.inpx` | Monsoon |
| `Lanka_S4_Night.inpx` | Night |

Opening them requires PTV VISSIM 2025 or later. Background satellite imagery is not embedded. A second
archived copy of Base, Lane_Block, Monsoon and Night, without signal heads, is *not* included; see
[docs/evidence_audit.md §6](../docs/evidence_audit.md#6-model-versions-signal-heads).

Key settings, as extracted into [`data/derived/inpx_settings.csv`](../data/derived/inpx_settings.csv):

| Setting | Value |
|---|---|
| VISSIM | 2025.00-11 and 2025.00-06 (two archived builds) |
| Simulation | 4,500 s; 10 steps/s (Lane_Block 15); seed 42, `numRuns = 1` |
| Evaluation | 600–4,200 s, 60 s intervals (queues: one interval) |
| Signal control | `FIXEDTIME`, 153 s; SG1 = East–West, SG2 = North–South; amber 3 s; intergreen 0 s |
| Queue counters | 1 N (link 2), 2 E (link 4), 3 S (link 6), 4 W (link 8) |
| Signal heads | 8 (2 lanes × 4 approaches) in every included model |
