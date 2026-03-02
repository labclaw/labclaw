---
name: data-format-adapter
description: >
  Use when the user has a data file in an unsupported format and needs to add a new
  loader to LabClaw's ingestion pipeline. Triggers include: "add support for SLEAP files,"
  "parse this .mat file," "load Suite2p data," "I have a new data format," "extend the
  data loader," "convert this file to LabClaw format." Covers neuroscience formats like
  SLEAP, DANNCE, Kilosort, Suite2p, and arbitrary CSV/JSON/HDF5 variants.
user-invocable: true
allowed-tools: Bash, Read, Edit, Write, Grep
context: fork
---

You are extending LabClaw's data ingestion system to handle a new file format.

## Supported formats (code handles these — fast, deterministic)

- **CSV/TSV/TXT**: flat tabular → list[dict]
- **SAM-Behavior H5**: `/positions` dataset (n_frames, n_animals, 2)
- **DeepLabCut H5**: MultiIndex DataFrame (scorer/individuals/bodyparts/coords)
- **NWB**: pynwb behavior processing module (Position / BehavioralTimeSeries)

## Output contract

All loaders must produce: `list[dict[str, Any]]`

Each dict = one observation. Numeric values as float, labels as str.
For tracking data: one row per (frame, animal).
Required keys for behavioral data: `frame`, `time_sec`, `animal_id`, `x`, `y`.
Additional format-specific keys are encouraged (e.g., `{bodypart}_x`, `{bodypart}_likelihood`
for pose estimation formats, `z` for 3D tracking, `value` or `col_N` for generic timeseries).

## How to add a new format

1. Read `src/labclaw/ingest.py` to understand existing loaders
2. Inspect the user's file: use h5py, pandas, or format-specific lib
3. Write `_load_newformat(path) -> list[dict[str, Any]]`
4. Add extension dispatch in `load_file()`
   - **For H5-based formats** (SLEAP, DANNCE, etc.): also update `_load_h5()` to sniff
     for format-specific keys (e.g., check for `/tracks` → SLEAP) before falling through
     to the DLC reader. The H5 dispatch chain in `_load_h5` uses key-sniffing, not extension.
5. Use `try/except ImportError` for any optional dependency
6. Write test in `tests/unit/test_ingest.py` with synthetic data
7. Run: `make test` (must pass at 100% coverage)

## Common format patterns

| Format | Extension | Key structure | Required lib |
|--------|-----------|---------------|-------------|
| SLEAP | .slp or .h5 | `/tracks` shape (n_frames, n_tracks, n_nodes, 2), `/node_names` | h5py |
| DANNCE | .mat | `predictions` key, shape (n_frames, n_joints, 3) | scipy.io |
| Suite2p | stat.npy + F.npy | folder with stat.npy (cell ROIs) + F.npy (fluorescence traces) | numpy |
| Kilosort | .npy | spike_times.npy + spike_clusters.npy in output folder | numpy |
| Generic JSON | .json | array of objects with timestamp + values | json (stdlib) |

## Checklist

- [ ] Loader returns `list[dict[str, Any]]`
- [ ] Optional deps guarded with `try/except ImportError`
- [ ] Extension added to `load_file()` dispatch
- [ ] For H5 formats: integrated into `_load_h5()` sniffing chain
- [ ] Test uses synthetic data (no real data files in repo)
- [ ] `make test` passes at 100% coverage
