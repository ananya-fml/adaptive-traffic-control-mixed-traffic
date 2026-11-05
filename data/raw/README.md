# Private raw evidence (not distributed)

This folder is git-ignored. The raw VISSIM exports and `.inpx` models are not published. They come from a
PTV VISSIM model built under a student licence, and permission to redistribute has not been confirmed.
They are available to reviewers on request from the author.

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

## Publishing the models later

If permission is granted to publish the `.inpx` models or CSV exports, place them outside `data/raw/`
(e.g. `vissim/models/`) and remove the `*.inpx` line from `.gitignore`. Otherwise git will silently skip them.
