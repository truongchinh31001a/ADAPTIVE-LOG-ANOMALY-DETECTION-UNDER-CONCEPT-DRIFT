# Frozen working research decisions

Updated: 25 September 2026. These decisions are frozen for the primary test unless the
supervisor explicitly requests a new experimental protocol. All numeric parameters were
selected from the BGL training/validation chronology; the held-out test chronology has
not been used for tuning.

## Dataset

- Primary dataset: BGL from the Loghub distribution.
- Provenance: Blue Gene/L logs from Lawrence Livermore National Laboratory; original
  citation is Oliner and Stearley (DSN 2007).
- Loghub inventory: 4,747,963 labeled lines covering 214.7 days.
- Use condition: research or academic use; retain the Loghub license notice, reference
  the repository, and cite the Loghub paper.
- Raw file must be stored unchanged under `data/bronze/bgl/` and registered with its
  SHA-256 before preprocessing.

Authoritative sources:

- https://github.com/logpai/loghub/tree/master/BGL
- https://github.com/logpai/loghub/blob/master/LICENSE
- https://doi.org/10.1109/ISSRE59848.2023.00071

## Parser

- Main parser: Drain via `drain3==0.9.11`.
- Feed only the unstructured message portion after the deterministic BGL header parser;
  timestamps, host, severity, and labels must not enter template mining.
- Freeze and archive the Drain configuration, masking rules, package version, and parser
  state checksum in each dataset manifest.
- Keep the supplied structured Loghub `EventId` path as a parser-sensitivity baseline,
  not as an interchangeable result source.
- Do not learn parser configuration from the test interval.

Rationale: Drain is an online fixed-depth parser and has a published streaming design.
Drain3 provides a reproducible implementation, while pinning version/config prevents
parser changes from being mistaken for template emergence.

Sources:

- https://doi.org/10.1109/ICWS.2017.13
- https://pypi.org/project/drain3/0.9.11/

## Detector

- Primary scientific detector: a DeepLog-style next-template LSTM trained on normal
  chronological sequences.
- Engineering sanity baseline: the existing template-frequency detector.
- Optional robustness detector, only if schedule permits: LogAnomaly or LogBERT.
- The policy and scenario code must depend on the detector protocol rather than on a
  detector-specific internal state.
- Primary prediction unit: next-event prediction aligned back to BGL event-level labels;
  window-level drift features remain separate from event-level F1.

Rationale: DeepLog is a published and recognizable sequence detector, is simpler to
reproduce than newer large encoders, and exposes degradation under changing event
sequences without making detector design the thesis contribution.

Sources:

- https://doi.org/10.1145/3133956.3134015
- https://doi.org/10.24963/ijcai.2019/658

## Scope and terminology

- Scientific object: the adaptation decision layer and its controlled evaluation.
- Observable drift mechanisms: template emergence and template-frequency drift.
- Temporal forms: sudden and gradual.
- Negative controls: transient anomaly burst and no drift.
- Do not claim that all frequency drift is real concept drift; report it as observable
  log-distribution drift and measure whether it degrades the detector.
- Primary metrics remain F1, Adaptation Delay, and False Adaptation Rate. Contamination,
  update cost, and drift-signal separability are diagnostic/secondary metrics.

## Frozen experiment snapshot

- Event-count window: 10,000 events.
- Chronological windows: train 0--94, validation 95--189, test 190--474.
- Primary evaluation horizons: validation 95--159 and test 190--259.
- Drain: version 0.9.11, similarity threshold 0.40, depth 4, maximum 100 children.
- Characterization: Jensen--Shannon threshold 0.05 and persistence signal threshold
  0.03.
- Proposed policy: minimum persistence 6 windows, three-window adaptation buffer,
  recurrence in all three windows and at least 200 events, rearm after three stable
  windows.
- Primary magnitude: 0.25; sensitivity magnitudes: 0.10 and 0.40.
- Validation seeds: 101, 202, 303. Held-out test seeds: 1101, 1202, 1303, 1404, 1505.

The machine-readable snapshot is `configs/experiments/frozen_test_v1.yaml`. No threshold,
policy, detector, scenario, or metric definition may be changed in response to primary
test results. Any later protocol change must create a separately named experiment.
