# Adaptive Log Anomaly Detection Under Concept Drift

Reproducible research pipeline for evaluating **when an existing log anomaly detector should adapt**
under template-frequency drift and template emergence. The repository implements the
minimum scope defined in `ADAPTIVE_LOG_ANOMALY_DETECTION_PROJECT_PLAN.md`:

- BGL-compatible preprocessing with chronological ordering;
- deterministic temporal windows and semi-synthetic scenarios S1-S6;
- a detector-neutral interface, a DeepLog-style next-template LSTM, and a reproducible
  template-frequency baseline;
- label-free adaptation candidate selection with recurrence-based spike filtering and
  auditable selected/rejected counts;
- drift characterization (new-template rate, Jensen-Shannon divergence, magnitude,
  persistence, and anomaly evidence);
- static, periodic, naive-triggered, and proposed drift-aware policies;
- F1, Adaptation Delay (AD), and False Adaptation Rate (FAR);
- manifests containing configs, seeds, checksums, and environment information.

The included demo data is synthetic and is only a smoke test. The reportable BGL results
are under `artifacts/bgl/test_primary_fixed/`; the direct RQ1--RQ3 answers are in
`reports/analysis.md`.

## Quick start

Prerequisites: Python 3.10+ and [uv](https://docs.astral.sh/uv/) (recommended).

```powershell
uv sync --extra dev --extra research
uv run adaptive-lad validate-configs
uv run adaptive-lad demo --clean
uv run pytest
```

The demo writes reproducible outputs to `artifacts/demo/`, including
`results_raw.parquet`, `summary.csv`, scenario ground truth, predictions, adaptation
events, and `experiment_manifest.json`.

## Use BGL data

1. Download BGL from its official/research distribution and keep the original file
   outside Git, for example `data/bronze/bgl/BGL.log`.
2. Do not redistribute the raw dataset without checking its license/terms.
3. Prepare event-level Parquet:

```powershell
uv run adaptive-lad prepare-bgl `
  --input data/bronze/bgl/BGL.log `
  --output data/silver/events/bgl_events.parquet `
  --parser drain3
```

Drain3 0.9.11 is the frozen main parser and receives only the unstructured BGL message
content. Structured LogPai-style CSV is supported with `--parser structured` when it
contains `Content` and preferably `EventId`/`EventTemplate` columns. The deterministic
regex parser remains available through `--parser regex` for parser-sensitivity checks.

Run one frozen scenario/method:

```powershell
uv run adaptive-lad run `
  --events data/silver/events/bgl_events.parquet `
  --scenario configs/scenarios/my_bgl_s1.yaml `
  --method proposed `
  --evaluation-split test `
  --output artifacts/bgl/s1/proposed
```

Run the frozen paired batch or rebuild its figures:

```powershell
uv run adaptive-lad batch-bgl `
  --events data/silver/events/bgl_events.parquet `
  --experiment-config configs/experiments/frozen_test_v1.yaml `
  --phase test `
  --output artifacts/bgl/test_reproduction

uv run python scripts/build_analysis.py
```

The root S1-S6 configs use the 200-event demo window. Frozen BGL variants live in
`configs/scenarios/bgl_validation/` and `configs/scenarios/bgl_test/`; they use disjoint
benign-emergence template pools. `--evaluation-split` restricts predictions and metrics
to that chronological split and automatically uses all earlier windows for offline
warm-up. The default scientific detector is `configs/detector/deep_log.yaml`; pass the
template-frequency config explicitly for the engineering baseline.

## Repository map

```text
configs/                  frozen data, detector, drift, policy, and experiment settings
data/                     bronze/silver/gold/scenario/result zones (large files ignored)
docs/                     architecture, contracts, and experiment protocol
literature/               literature matrix and review notes
notebooks/                exploratory work only; production logic lives in src/
reports/                  report notes plus generated figure/table destinations
scripts/                  convenience commands for setup and quality checks
src/adaptive_lad/         tested research pipeline
tests/                    unit and end-to-end reproducibility tests
artifacts/                generated models, manifests, logs, and demo outputs
```

## Reproducibility rules

1. Ground truth is generated and saved before a policy is run.
2. A policy never receives drift labels or valid-adaptation intervals at inference time.
3. Split assignment is chronological and generated once per processed dataset.
4. Validation configs/seeds may be tuned; test configs/seeds remain frozen.
5. Every reported result points to its config snapshot and experiment manifest.
6. Raw/intermediate data and generated artifacts are ignored by Git; metadata/configs
   remain tracked.

See [docs/experiment_protocol.md](docs/experiment_protocol.md) before running thesis
experiments and [docs/data_contracts.md](docs/data_contracts.md) before changing schemas.
