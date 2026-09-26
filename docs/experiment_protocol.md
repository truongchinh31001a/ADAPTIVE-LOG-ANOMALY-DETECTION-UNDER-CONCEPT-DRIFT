# Frozen experiment protocol

## Before any final test run

1. Register and checksum the raw BGL file.
2. Freeze parser, event schema, temporal window size, and chronological split boundaries.
3. Freeze scenario configs, magnitudes, held-out emergence templates, and test seeds.
4. Generate scenario streams and ground truth before running any policy.
5. Tune thresholds only on validation scenarios/seeds.
6. Snapshot every resolved config and software environment in a manifest.

## Scenario semantics

- S1: sudden persistent template-frequency drift; adaptation required.
- S2: gradual persistent template-frequency drift; adaptation required.
- S3: sudden emergence of held-out normal templates; adaptation required.
- S4: gradual emergence of held-out normal templates; adaptation required.
- S5: temporary anomaly burst; adaptation forbidden.
- S6: no drift; adaptation forbidden.

S1--S6 use a controlled stationary backbone rather than untreated BGL chronology.
The backbone replays the latest eligible clean pre-evaluation window (at least three
templates and two with frequency >= 0.10) and adds a fixed 0.5% background anomaly
rate. This makes S6 a genuine negative control. Untreated chronological BGL is reported
separately as an ecological/natural-evolution analysis and has no claimed drift ground
truth.

For gradual drift, the valid interval begins at transition start. For sudden drift it
begins at the first target-regime window. The interval ends after the configured
tolerance horizon. Missed adaptation is reported separately and AD is censored at the
horizon. All actions outside valid intervals count toward FAR.

## Required comparisons

Static, periodic retraining, naive drift-triggered adaptation, and the proposed
drift-aware policy must use identical streams, seeds, detector implementation, and
evaluation code.

## Reporting

Report each seed, mean, standard deviation, and failures—not only the best run. Keep F1,
AD, and FAR primary. Any auxiliary diagnostic metric must be labeled exploratory.
The primary experiment uses magnitude 0.25 over five disjoint test seeds. Magnitudes
0.10 and 0.40 are sensitivity checks on one frozen test seed. Validation seeds
101/202/303 and test seeds 1101/1202/1303/1404/1505 are disjoint.
