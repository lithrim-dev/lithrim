# Data Manifest

The Synthea sample CSV cohort is NOT checked into this repo (147MB). It's pinned by path.

## Expected layout

```
data/synthea_sample_data_csv_latest/
├── patients.csv
├── encounters.csv
├── medications.csv
├── conditions.csv
├── allergies.csv
├── observations.csv
├── procedures.csv
└── ... (others ignored for v1)
```

## How to provide it

**Option A (local, fastest):** symlink or copy an existing local checkout of the cohort
into place (the path is gitignored either way):

```bash
ln -s /path/to/synthea_sample_data_csv_latest data/synthea_sample_data_csv_latest
```

**Option B (fresh download):** the Synthea sample cohort can be regenerated with the [Synthea](https://github.com/synthetichealth/synthea) Java generator, or downloaded from the project's public sample tarball. Pin the seed before regenerating; the bench's reproducibility claim depends on it.

## Provenance fields

Every generated case records, in its `synthea_provenance` block:

- `cohort_path` — relative to repo root
- `cohort_sha256` — hash of `patients.csv` (cheap proxy for the cohort)
- `synthea_version` — version string, manually recorded; will be auto-derived once `data/SYNTHEA_VERSION` file is added

The bench's `Lint + OwnerMatrix gate` (phase 1) does not yet enforce a single pinned `cohort_sha256`. That gate ships in phase 2.
