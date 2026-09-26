# Architecture

```text
raw/structured logs
        |
        v
chronological events + templates -----> scenario generator -----> frozen ground truth
        |                                      |
        v                                      v
detector interface --------------------> scenario stream
        |                                      |
        +---------- predictions <--------------+
                           |
                           v
rolling drift characterization (no ground truth)
                           |
                           v
static | periodic | naive | proposed policy
                           |
                           v
optional detector update + decision audit trail
                           |
                           v
F1 + Adaptation Delay + False Adaptation Rate + manifest
```

The scenario generator and evaluator may read ground truth. The detector,
characterizer, and policy may not. `ExperimentRunner` enforces this boundary by only
passing per-window events, scores, and characterization features to policy objects.

The primary detector is a DeepLog-style next-template LSTM: chronological sequences are
formed per host, the model is fitted on normal-labelled offline training events, and an
event is anomalous when its observed template is absent from the top-k next-template
candidates. The template-frequency detector remains an interpretable engineering
baseline. Both use the same `Detector` protocol, scenarios, policy, and metrics.

DeepLog vocabulary expansion is permitted only after the policy requests adaptation.
The update combines the policy-selected pseudo-normal events with a bounded chronological
replay buffer and fine-tunes the model. Ground-truth labels are removed before that path.

Before an adaptation update, the runner removes all ground-truth columns and applies an
observable pseudo-normal selection rule. Predicted-normal, low-score events are eligible;
high-score events are eligible only when their template recurs across the configured
minimum number of windows and events. Recurrence lets persistent frequency shifts and
template emergence enter the update while rejecting one-window spikes. Selection and
rejection counts are kept in the adaptation audit trail so contamination controls can be
reported and ablated.

The template-frequency engineering baseline can recalibrate its decision threshold from
the selected pseudo-normal update set. Both recalibration and its update rate are frozen
detector configuration parameters so a fixed-threshold ablation uses the same pipeline.
