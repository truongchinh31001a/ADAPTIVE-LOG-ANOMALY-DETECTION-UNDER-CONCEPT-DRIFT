# Final experimental analysis

## Evidence and protocol

The primary result contains 120 unique held-out test runs: six scenarios, four methods,
and five frozen test seeds (1101, 1202, 1303, 1404, 1505). The primary injected
magnitude is 0.25; S6 has no magnitude. Results are paired within each seed because the
four methods receive deep copies of the same fitted DeepLog checkpoint and the same
generated stream. Values below are mean +/- sample standard deviation across five seeds.

The final primary artefact is `artifacts/bgl/test_primary_fixed/`. Its 40 S1--S2 rows
replace an earlier run after an audit found that iteration over a Python set made the
frequency generator depend on `PYTHONHASHSEED`. The generator now uses a stable sorted
order and a cross-process regression test. S3--S6 were retained only after their stream
SHA-256 values matched across independent processes. The replacement and source hashes
are recorded in the merge manifest.

| Scenario | Static F1 | Periodic F1 | Naive F1 | Proposed F1 | Proposed post-update F1 | Proposed AD | Proposed FAR | Proposed updates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 sudden frequency | .286 +/-.023 | .893 +/-.234 | .921 +/-.006 | .715 +/-.017 | .993 +/-.009 | 5.0 +/-0.0 | 0 | 1 |
| S2 gradual frequency | .245 +/-.020 | .994 +/-.008 | .883 +/-.022 | .793 +/-.024 | .993 +/-.009 | 11.8 +/-.4 | 0 | 1 |
| S3 sudden emergence | .045 +/-.000 | .320 +/-.005 | .177 +/-.006 | .259 +/-.015 | .526 +/-.092 | 5.0 +/-0.0 | 0 | 1 |
| S4 gradual emergence | .045 +/-.000 | .512 +/-.007 | .420 +/-.002 | .302 +/-.002 | .484 +/-.006 | 8.0 +/-0.0 | 0 | 1 |
| S5 transient anomaly | .992 +/-.001 | .943 +/-.000 | .653 +/-.002 | .992 +/-.001 | n/a | n/a | 0 | 0 |
| S6 no injected drift | .965 +/-.005 | .997 +/-.000 | .965 +/-.005 | .965 +/-.005 | n/a | n/a | 0 | 0 |

![Primary F1](figures/primary_f1.png)

## RQ1 -- What is the effect of drift on a static detector?

The static DeepLog detector is strong in the two controls (F1 .992 on S5 and .965 on
S6), but degrades sharply after persistent injected drift: overall F1 is .286 on S1,
.245 on S2, and only .045 on both emergence scenarios. Relative to S6, this is a loss
of .679--.921 absolute F1. Its detector predictions cross the adaptation-success
criterion after the drift onset, but because static never updates these are recorded as
missed adaptations; the observed delays are the right-censored horizons (5, 25, 5, and
15 windows for S1--S4).

Answer to RQ1: both template-frequency drift and template emergence substantially
degrade the frozen sequence detector under the controlled BGL protocol. Emergence is
more damaging because previously held-out normal templates are initially treated as
unexpected next events.

## RQ2 -- Can observable signals distinguish persistent drift from anomaly bursts?

The characterization layer combines Jensen--Shannon template-distribution divergence,
new-template rate, and model anomaly evidence. On the seed-1101 diagnostic replay,
pre-drift divergence is approximately .0025. S1--S4 reach persistence 6 and trigger one
action; S5 produces a large but five-window transient and never reaches the required
persistence; S6 remains near baseline with maximum drift magnitude .00285 and
persistence zero.

| Scenario | Peak divergence | Peak new-template rate | Peak anomaly evidence | Max persistence | Action window |
|---|---:|---:|---:|---:|---:|
| S1 | .1400 | .0001 | .0549 | 6 | 225 |
| S2 | .0827 | .0001 | .0353 | 6 | 212 |
| S3 | .1403 | .2488 | .2543 | 6 | 205 |
| S4 | .1130 | .0226 | .2089 | 6 | 203 |
| S5 | .1403 | .0817 | .2543 | 5 | none |
| S6 | .0026 | .0035 | .0055 | 0 | none |

![Drift signals](figures/drift_signals.png)

Answer to RQ2: magnitude alone is insufficient because S5 can look stronger than a real
drift window. Persistence plus the transient guard separates S5 from S1--S4 in this
protocol. New-template rate distinguishes emergence from frequency drift, while S6
establishes the stationary signal floor. These are controlled separability results, not
a claim that the same thresholds transfer unchanged to every production log stream.

## RQ3 -- Does selective adaptation improve quality without unsafe updates?

Compared with static, the proposed method raises overall F1 by .429 (S1), .549 (S2),
.215 (S3), and .257 (S4). More importantly, after its first update it reaches F1 .993
for both frequency scenarios and .526/.484 for sudden/gradual emergence. The proposed
method performs exactly one update in every primary S1--S4 run, no update in any S5--S6
run, and therefore has FAR 0 across all five test seeds.

The safety filter is observable-label-free. In the seed-1101 primary diagnostics each
action receives 30,000 buffered events. It rejects all 150 fixed background anomalies
in S1/S2 and rejects 475/393 events in S3/S4; recurrent newly emerged templates remain
eligible. No evaluation label is present in the update buffer.

The benefit has a real latency cost. Naive adapts at delay 0/7.8/0/4 windows for
S1--S4 and periodic at delay 4, so their overall F1 is often higher before the proposed
policy acts. However, naive false-adapts on S3 and S5 (mean FAR .0156 and .0143), and its
S5 F1 falls to .653. Periodic makes 14 updates per run and has FAR about .20 on both
negative controls. The proposed method preserves static F1 exactly on S5 and S6 while
using one update rather than 14 in persistent-drift runs.

![Adaptation trade-off](figures/adaptation_tradeoff.png)

Answer to RQ3: selective adaptation produces a conservative safety--latency trade-off.
It is not the highest-overall-F1 policy in every scenario, but it restores the detector
after persistent drift with zero observed false adaptations and far fewer updates. This
supports the thesis contribution as an adaptation-decision layer, not as a universally
better anomaly detector.

## Sensitivity analysis

Sensitivity was frozen before the primary test and uses seed 1101 at magnitudes .10 and
.40. Proposed FAR remains zero and it never adapts in S5 or S6. Stronger gradual drift
is detected earlier (S2 AD 23 -> 9; S4 AD 14 -> 7). Sudden scenarios remain at AD 5,
the minimum allowed by the six-window persistence rule. Overall F1 can decrease as
magnitude rises because more events are exposed before the action; post-update F1 still
reaches 1.0 in frequency drift and .56--.70 in emergence.

One sensitivity failure mode is explicit: S2 at magnitude .40 produces two adaptation
actions. The strong gradual change briefly rearms after the first reference rebase. FAR
remains zero because both actions occur in a valid persistent-drift region, but this
shows that the one-update invariant is specific to the primary magnitude and should not
be generalized. Future work should test a longer rearm horizon or change-point episode
tracking on validation data in a separately named protocol.

![Sensitivity](figures/sensitivity.png)

## Threats to validity and scope

- S1--S6 use stationary replay of real BGL windows plus controlled injections. This
  gives identifiable ground truth but does not reproduce every dependency in the raw
  chronological stream.
- Natural chronological BGL has substantial native regime changes and cannot serve as
  a no-drift control. A pilot produced many false positives; it is ecological evidence,
  not an identifiable adaptation benchmark.
- Five test seeds support variability estimates but are too few for strong asymptotic
  significance claims. The report therefore emphasizes paired effects and mean +/- SD,
  not p-value-driven conclusions.
- Only one parser (Drain3) and one primary detector family (DeepLog-style LSTM) are used.
  Parser errors and detector choice may change absolute results.
- Emergence post-update F1 remains materially below frequency-drift performance. The
  limitation belongs mainly to learning previously unseen sequential context, not just
  deciding when to adapt.
- BGL is one HPC dataset. External validity requires another system/domain and a
  naturally annotated drift benchmark when one becomes available.

## Reproducibility pointers

- Frozen protocol: `configs/experiments/frozen_test_v1.yaml`
- Primary raw results and summary: `artifacts/bgl/test_primary_fixed/`
- Sensitivity results: `artifacts/bgl/test_sensitivity_fixed_seed1101/`
- Window-level diagnostics: `artifacts/bgl/test_diagnostics_frequency_fixed_seed1101/`
  and `artifacts/bgl/test_diagnostics_seed1101/`
- Drift-signal table: `reports/tables/drift_signal_summary.csv`
- Figure generator: `scripts/build_analysis.py`
- Result merge/audit utility: `scripts/summarize_results.py`
