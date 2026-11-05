# Private raw evidence (not distributed)

This folder is git-ignored. The raw VISSIM CSV exports are not published; they are available to reviewers
on request from the author. The five correct `.inpx` models *are* published, in
[`vissim/models/`](../../vissim/models).

To regenerate `data/derived/`, extract the archives so that this folder looks like:

```
data/raw/
├── results/        # from results.zip      → Base/ Encroach/ Lane_Block/ Monsoon/ Night/ + "ug final final.py"
└── ug_results/     # from ug_results.zip   → same layout
```

then run `make audit`. Expected checksums for every raw file are in
[`../derived/raw_manifest.csv`](../derived/raw_manifest.csv) (CSV exports) and
[`../derived/inpx_settings.csv`](../derived/inpx_settings.csv) (models). The 30 CSV exports are
byte-identical between the two archives.
