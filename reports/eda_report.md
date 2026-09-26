# BGL temporal EDA and frozen data protocol

## Dataset and split

The immutable source is the Loghub BGL archive recorded in
`data/metadata/dataset_registry/bgl.yaml`. The archive MD5 is
`4452953c470f2d95fcb32d5f6e733f7a`; the raw log SHA-256 is
`666130b15ef44eb32fd02bd053e6c6e007c37696b5e7e8b9d8e45b729876a5d2`.
Drain3 0.9.11 (similarity 0.40, depth 4, max children 100) produced the frozen
event table with SHA-256
`03c06bbc4b2a50c152bc4c331d361351938168c9256a3d8f10815a424ccdbd9f`.

The table contains 4,747,963 events, of which 4,399,503 are normal and 348,460
are anomalous, spanning 2005-06-03 22:42:50 UTC through 2006-01-04 16:00:05
UTC. Drain produced 1,823 templates. Stable chronological sorting precedes both
windowing and splitting; equal timestamps retain source-file order.

| Split | Window IDs | Events | Templates | Anomaly ratio | UTC interval |
|---|---:|---:|---:|---:|---|
| Train | 0--94 | 950,000 | 301 | 23.6759% | 2005-06-03 22:42:50 to 2005-06-25 10:34:23 |
| Validation | 95--189 | 950,000 | 194 | 0.3181% | 2005-06-25 10:34:23 to 2005-07-10 04:09:51 |
| Test | 190--474 | 2,847,963 | 1,665 | 4.2317% | 2005-07-10 04:09:51 to 2006-01-04 16:00:05 |

Boundary timestamps can occur on both sides because many records share the same
second; assignment is nevertheless unambiguous by source order and window ID.
Window 474 is the only partial window (7,963 events).

## Window-size justification

Window size was selected using only the first 40% chronology (train plus
validation). This is a count-window design because BGL arrival intensity varies
sharply: the median and 95th-percentile duration of a 10,000-event window are
0.357 and 27.154 hours. Time windows would therefore have highly variable sample
sizes and unstable template-frequency estimates.

| Events/window | Development windows | Median duration (h) | P95 duration (h) | Median templates | Anomaly-free windows | Median JS | P95 JS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5,000 | 380 | 0.051 | 17.628 | 3 | 72.82% | 0.0178 | 0.8070 |
| **10,000** | **190** | **0.357** | **27.154** | **5** | **62.96%** | **0.1149** | **0.8172** |
| 20,000 | 95 | 0.896 | 41.393 | 9 | 51.06% | 0.1589 | 0.8818 |

The frozen choice is 10,000 events: 5,000-event windows are often too sparse
(median three templates), while 20,000 events halves temporal resolution and
extends the already-long high-traffic-gap windows. The choice is a pragmatic
resolution/stability compromise, not evidence that 10,000 is universally
optimal. Window size will be reported as a sensitivity factor.

## Temporal findings

`artifacts/bgl/eda/temporal_signals.png` shows large, intermittent changes in
template count, new-template event rate, anomaly prevalence, and Jensen-Shannon
divergence. The signals do not move together consistently: a distribution shift
is not automatically an anomaly burst. This supports the thesis design of
combining magnitude, novelty, persistence, and anomaly evidence before adapting.

`artifacts/bgl/eda/top_template_frequency.png` shows regime changes among the ten
globally most frequent templates. It is descriptive only; neither the test
labels nor this global ranking are used to set thresholds or train a model.

The first fifth of the stream is unusually anomaly-heavy (23.68%), so the study
uses semi-supervised offline fitting on normal-labelled **training** events. This
is preferable to silently treating every warm-up event as normal. Validation and
test labels remain evaluation-only.

## Held-out benign emergence templates

Synthetic emergence scenarios draw only from templates whose first occurrence
is in the target split, have zero labelled anomaly events, at least 500 total
events, and activity in at least two windows. Candidates are ordered by first
timestamp then template ID; the first five are frozen in
`configs/data/bgl_heldout_templates.yaml`. Validation templates are used while
tuning; the disjoint test list is used only for frozen final evaluation.

## Leakage checks

- Drain parsing is online and chronological; templates are not fitted by a
  separate pass over future messages.
- Split assignment is by complete count windows, never random rows.
- Window size and policy hyperparameters are selected on train/validation only.
- Training labels may filter the offline normal set. Validation/test labels are
  passed only to metric computation, not to characterization, decisions, or
  adaptation candidate selection.
- Adaptation buffers explicitly remove `anomaly_label` and `drift_label`; updates
  use low-risk predictions or recurrent novelty as pseudo-normal evidence.
- Test results are inspected only after configuration is copied to a frozen
  experiment snapshot.

## Limitations to report

Count windows represent unequal elapsed time, so Adaptation Delay must be
reported in both windows and elapsed time where applicable. BGL labels denote
system alerts rather than a complete causal annotation of every distribution
change. Consequently, the thesis should call the observable phenomenon
*log-distribution drift* (or virtual drift), not claim that every JS spike is a
change in the latent anomaly concept.
