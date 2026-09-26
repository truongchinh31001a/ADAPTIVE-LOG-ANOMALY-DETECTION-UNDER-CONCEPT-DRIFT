# Validation tuning record

All choices below use BGL train/validation windows only. Test windows, test seeds,
and test metrics were not consulted. The frozen test snapshot is
`configs/experiments/frozen_test_v1.yaml`.

## Controlled backbone

Using raw chronological BGL as S6 was rejected because temporal EDA and the initial
pilot showed substantial natural regime changes: the static DeepLog model had recall
1.0 but 38,224 false positives on validation. A no-injected-drift stream is therefore
not a no-drift control.

The controlled S1--S6 protocol replays one real anomaly-free pre-evaluation window and
adds a fixed 0.5% background anomaly rate sampled from earlier labelled anomalies. The
reference window must contain at least three templates, with at least two templates at
frequency >= 0.10. The latest eligible validation window is 92. This gives a stable
S6 while preserving real BGL messages, hosts, templates, and sequences.

## Policy decisions

- JS threshold: 0.05; stable S6 is approximately 0.0025 and magnitude-0.25 S1 is
  approximately 0.067.
- Magnitude/persistence signal threshold: 0.03.
- Minimum persistence: six windows. The S5 burst lasts five windows, whereas persistent
  S1--S4 remains active; this yields maximum allowed AD=5 for sudden drift.
- Hysteresis: one action per uninterrupted regime signal; rearm after three stable
  windows.
- Adaptation buffer: three windows. Recurrent high-score templates require all three
  windows and at least 200 events. The fixed background contributes only 150 anomaly
  events to a complete buffer, so this rule blocks them without reading labels.
- DeepLog update: five epochs with a 20,000-event replay buffer. The update is a
  detector implementation choice, not the proposed contribution.

## Three-seed validation evidence at magnitude 0.25

Values are mean +/- sample standard deviation across validation seeds 101, 202, and 303.

| Scenario | Static F1 | Proposed F1 | Proposed post-adaptation F1 | AD | FAR | Actions |
|---|---:|---:|---:|---:|---:|---:|
| S1 sudden frequency | .156 +/-.011 | .520 +/-.018 | .915 +/-.005 | 5.0 +/-0.0 | 0 | 1 |
| S2 gradual frequency | .141 +/-.010 | .426 +/-.022 | .909 +/-.014 | 13.0 +/-0.0 | 0 | 1 |
| S3 sudden emergence | .060 +/-.000 | .281 +/-.000 | .772 +/-.014 | 5.0 +/-0.0 | 0 | 1 |
| S4 gradual emergence | .054 +/-.000 | .354 +/-.004 | .774 +/-.016 | 8.0 +/-0.0 | 0 | 1 |
| S5 transient anomaly | .959 +/-.009 | .959 +/-.009 | n/a | n/a | 0 | 0 |
| S6 no drift | .835 +/-.037 | .835 +/-.037 | n/a | n/a | 0 | 0 |

Periodic adaptation often achieves high F1 but performs 13 updates and FAR about 0.20.
Naive adaptation reacts earlier but false-adapts in S5 and reduces S5 F1 to 0.403.
These results establish the intended trade-off consistently across all three seeds.
The proposed method adapts exactly once in persistent S1--S4, never in negative-control
S5--S6, and reaches post-adaptation F1 from .772 to .915. The complete machine-readable
evidence is under `artifacts/bgl/validation_final/`. The protocol is now frozen before
the held-out test run.
