# ADAPTIVE LOG ANOMALY DETECTION UNDER CONCEPT DRIFT
## A Drift-Aware Adaptation Policy

**Student:** Phạm Trường Chinh  
**Research area:** Data Mining  
**Subfield:** Concept Drift / Stream Mining / Log Anomaly Detection  
**Target reporting period:** January 2027

---

# 1. Project Overview

## 1.1. Research problem

Log anomaly detection is commonly built under the assumption that the underlying log distribution remains relatively stable over time. In evolving software systems, this assumption can be violated by software updates, workload changes, service additions, configuration changes, and changes in logging behavior.

When the log distribution changes, a static anomaly detector may classify newly valid behavior as anomalous, which can reduce detection performance and increase false alarms.

This project studies **log anomaly detection under concept drift**, with a focus on building a **drift-aware adaptation policy** that can determine **whether and when** an existing anomaly detector should adapt.

The study does **not** focus on creating a new anomaly detector. Existing detectors are used as the underlying detection component.

---

# 2. Core Research Direction

The project focuses on the following research chain:

```text
Log Stream
   ↓
Existing Anomaly Detector
   ↓
Drift Monitoring
   ↓
Drift Characterization
   ↓
Drift-Aware Adaptation Policy
   ↓
Adapt / Do Not Adapt
   ↓
Updated Detector
   ↓
Evaluation
```

The core idea is:

```text
WHAT CHANGED?
      ↓
Drift Characterization

SHOULD THE MODEL ADAPT?
      ↓
Adaptation Decision

WHEN SHOULD IT ADAPT?
      ↓
Adaptation Timing
```

---

# 3. Research Scope

## 3.1. Drift types included

The project focuses on only two forms of concept drift that are directly observable from log structure and distribution.

### A. Template Emergence

New valid log templates appear over time.

Example:

```text
Before:
T1, T2, T3

After:
T1, T2, T3, T7, T8
```

### B. Template Frequency Drift

The frequency distribution of existing log templates changes over time.

Example:

```text
Before:
T1 = 60%
T2 = 30%
T3 = 10%

After:
T1 = 20%
T2 = 30%
T3 = 50%
```

## 3.2. Temporal forms

Both drift types are evaluated under:

- Sudden drift
- Gradual drift

## 3.3. Out of scope

The following are not primary research targets:

- Semantic drift
- Designing a new anomaly detector
- Complex continual learning methods
- LLM-based anomaly detection
- Data Lake as a scientific contribution
- Production-grade Kafka/streaming infrastructure
- Large-scale MLOps architecture

If a Data Lake is used, it serves only as research-data infrastructure.

---

# 4. Research Objectives

## General objective

Develop and evaluate a **drift-aware adaptation policy** for log anomaly detection under concept drift.

## Specific objectives

1. Evaluate how template emergence and template frequency drift affect static log anomaly detectors.
2. Characterize drift using temporal quantitative signals.
3. Build an adaptation policy that decides whether adaptation is necessary and when adaptation should occur.
4. Evaluate the proposed policy using a transparent, reproducible, semi-synthetic protocol independent of the proposed method.

---

# 5. Research Questions

## RQ1

**How do template emergence and template frequency drift affect the performance of static log anomaly detectors?**

## RQ2

**How can template emergence and template frequency drift be effectively characterized in evolving log streams?**

## RQ3

**How can a drift-aware adaptation policy use drift characteristics to determine whether and when an existing log anomaly detector should adapt?**

---

# 6. Initial Research Hypotheses

## H1

Concept drift reduces the effectiveness of static log anomaly detectors, especially when new templates emerge or template-frequency distributions change significantly.

## H2

A drift-aware adaptation policy based on drift characteristics can maintain anomaly-detection performance better than static models and fixed-update strategies while reducing unnecessary adaptations.

---

# 7. Proposed Research Architecture

```text
                         LOG STREAM
                             │
                             ▼
                       Log Parsing
                             │
                             ▼
                    Log Representation
                             │
                             ▼
                 Existing Anomaly Detector
                             │
                     Anomaly Prediction
                             │
                             ▼
                      Drift Monitoring
                             │
                             ▼
               ┌────────────────────────┐
               │ Drift Characterization │
               │                        │
               │ - New-template rate    │
               │ - Frequency changes    │
               │ - Divergence           │
               │ - Drift magnitude      │
               │ - Persistence          │
               └───────────┬────────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Drift-Aware         │
                │ Adaptation Policy   │
                └──────────┬──────────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
              No Adapt            Adapt
                                      │
                                      ▼
                               Updated Detector
                                      │
                                      ▼
                             F1 / AD / FAR
```

---

# 8. Drift Characterization

The drift-characterization component describes the current state of distribution change before the adaptation policy makes a decision.

## Candidate signals

- New-template rate per temporal window
- Template-frequency distribution
- Distribution divergence between current and reference windows
- Drift magnitude
- Drift persistence across windows
- Anomaly evidence from the underlying detector

## Expected output

For each temporal window:

```text
window_id
timestamp_start
timestamp_end
new_template_rate
template_frequency_vector
distribution_divergence
drift_magnitude
persistence
anomaly_evidence
```

The goal is not only to answer:

> Is there a change?

but also:

> What type of change is occurring, how strong is it, and how persistent is it?

---

# 9. Drift-Aware Adaptation Policy

## Inputs

The policy may receive:

- Drift type
- Drift magnitude
- Persistence
- New-template rate
- Distribution-change score
- Anomaly evidence

## Main decision

```text
Adapt?
   ├── No
   └── Yes
```

The primary research focus is:

> **Whether and when the detector should adapt.**

The detailed update mechanism is an implementation choice rather than the main research contribution.

Possible implementation actions may include:

- No adaptation
- Lightweight update
- Model update / retraining

---

# 10. Research Data

## 10.1. HDFS

Role:

- Establish baseline log anomaly detection
- Validate preprocessing and detector pipeline

Status:

- Secondary dataset
- Can be reduced or omitted if the schedule becomes tight

## 10.2. BGL

Role:

- Main research dataset
- Temporal analysis
- Semi-synthetic drift construction
- Adaptive evaluation

**BGL is the primary dataset of the project.**

## 10.3. Thunderbird

Role:

- Optional external validation
- Scalability/generalization study

Status:

- Stretch goal only
- Not required for the core thesis

---

# 11. Data Organization

Recommended research-data structure:

```text
data/
├── bronze/
│   └── bgl/
│       └── raw logs
│
├── silver/
│   ├── events/
│   ├── templates/
│   ├── labels/
│   └── sequences/
│
├── gold/
│   ├── anomaly_detection/
│   ├── drift_detection/
│   └── adaptive_learning/
│
├── drift_scenarios/
│   ├── S1/
│   ├── S2/
│   ├── S3/
│   ├── S4/
│   ├── S5/
│   └── S6/
│
├── metadata/
│   ├── dataset_registry/
│   ├── configs/
│   └── ground_truth/
│
└── results/
    ├── baseline/
    ├── drift/
    └── adaptation/
```

Recommended format:

- Raw logs: original `.log/.txt`
- Processed data: Parquet
- Configurations: YAML/JSON
- Results: CSV/Parquet + figures

---

# 12. Main Data Schema

## 12.1. Event-level data

```text
event_uid
timestamp
dataset
host
component
raw_message
parsed_message
template_id
parameters
anomaly_label
```

## 12.2. Window-level data

```text
window_id
start_time
end_time
num_events
num_templates
num_new_templates
new_template_rate
template_frequency_vector
distribution_divergence
drift_magnitude
persistence
anomaly_ratio
drift_label
```

---

# 13. Ground-Truth Concept Drift Protocol

The study uses **semi-synthetic drift** built from real log data.

The purpose is to obtain controlled and reproducible drift ground truth.

## Mandatory principles

1. The drift generator is independent of the proposed adaptation policy.
2. All drift-generation parameters are stored in configuration files.
3. Ground-truth labels are created before the proposed method is executed.
4. Drift/adaptation hyperparameters are tuned only on validation scenarios.
5. Test scenarios and test random seeds remain isolated.
6. Every scenario is executed using multiple random seeds.
7. The same configuration must regenerate the same drift scenario.

## Required configuration

```yaml
scenario_id:
drift_type:
temporal_pattern:
start_window:
end_window:
drift_magnitude:
affected_templates:
window_size:
random_seed:
```

---

# 14. Semi-Synthetic Drift Generation

## 14.1. Template-Frequency Drift

The target distribution is generated by changing the occurrence rates of existing normal templates.

Example:

```text
Source distribution:
T1 = 60%
T2 = 30%
T3 = 10%

Target distribution:
T1 = 20%
T2 = 30%
T3 = 50%
```

The distribution is defined before the proposed method is run.

## 14.2. Template-Emergence Drift

New templates are taken from:

- normal templates in a held-out portion of the dataset; or
- normal templates appearing in later temporal periods.

They are introduced according to predefined:

- start time
- emergence rate
- drift magnitude
- temporal pattern

They must not be selected based on the performance of the proposed method.

---

# 15. Main Experimental Scenarios

| Scenario | Type | Description | Expected Policy |
|---|---|---|---|
| S1 | Sudden Frequency Drift | Sudden change in template-frequency distribution | Adapt |
| S2 | Gradual Frequency Drift | Distribution changes gradually across windows | Adapt |
| S3 | Sudden Template Emergence | New normal templates appear suddenly | Adapt |
| S4 | Gradual Template Emergence | New normal templates appear progressively | Adapt |
| S5 | Transient Anomaly Burst | Temporary anomaly changes distribution but does not create a new normal regime | Do NOT adapt |
| S6 | No-Drift Control | No injected drift | Do NOT adapt |

S5 and S6 are critical negative controls for measuring incorrect adaptation behavior.

---

# 16. Correct Adaptation Definition

Each drift episode has a predefined ground-truth interval.

## Sudden drift

```text
drift_start = first window of target regime
```

## Gradual drift

```text
drift_start = beginning of transition
drift_end   = end of transition
```

An adaptation is considered valid if it occurs:

- inside the drift interval; or
- within a predefined tolerance horizon `H`.

Adaptation during:

- no-drift regions
- transient-anomaly regions

is counted as false adaptation.

The adaptation policy must never access ground-truth drift intervals during inference.

---

# 17. Primary Evaluation Metrics

The study deliberately focuses on only three primary metrics.

## 17.1. F1-score

Purpose:

> Measure anomaly-detection quality.

Evaluation periods:

- Before drift
- During drift
- After adaptation

Desired direction:

> Higher is better.

---

## 17.2. Adaptation Delay (AD)

Measures the delay between the beginning of ground-truth drift and the first valid adaptation.

```text
AD = t_adapt - t_drift
```

Main unit:

> Number of temporal windows.

If no valid adaptation occurs within evaluation horizon `H`:

- record the case as **missed adaptation**
- treat AD as censored at `H` according to the predefined evaluation protocol

Desired direction:

> Lower is better, provided adaptation is not premature.

---

## 17.3. False Adaptation Rate (FAR)

Measures adaptation actions occurring when adaptation is not required.

Relevant regions:

- Transient anomaly burst
- No-drift control
- Other invalid adaptation intervals

Conceptually:

```text
FAR =
false adaptation actions
-------------------------
non-valid adaptation windows
```

Desired direction:

> Lower is better.

---

# 18. Baselines

The proposed method should be compared with at least:

## B1. Static Detector

```text
Train once
→ Never update
```

## B2. Periodic Retraining

```text
Every N windows
→ Update detector
```

No drift evidence is used.

## B3. Naive Drift-Triggered Adaptation

```text
Drift alarm
→ Adapt immediately
```

No detailed adaptation policy.

## B4. Proposed Drift-Aware Adaptation Policy

```text
Drift characteristics
→ Adaptation decision
→ Adapt / Do not adapt
```

---

# 19. Expected Research Contributions

## Contribution 1 — Drift Characterization

A temporal representation of:

- template emergence
- template-frequency drift
- drift magnitude
- drift persistence

for adaptation decision-making.

## Contribution 2 — Drift-Aware Adaptation Policy

A policy that determines:

> whether and when an existing log anomaly detector should adapt.

## Contribution 3 — Reproducible Evaluation Protocol

A semi-synthetic evaluation framework containing:

- sudden drift
- gradual drift
- negative controls
- ground-truth intervals
- fixed configurations
- random seeds
- predefined adaptation-evaluation rules

---

# 20. Main Research Risks

| Risk | Control |
|---|---|
| Biased drift ground truth | Freeze generator, configs, test seeds before final evaluation |
| Semi-synthetic scenarios are unrealistic | Generate drift from real BGL templates/distributions |
| Policy overfits one detector | Use a detector-neutral interface; multi-detector validation only if time permits |
| Temporal leakage | Maintain chronological train/validation/test order |
| Scope expansion | Keep only template emergence + frequency drift |
| Too many evaluation metrics | Keep F1 + AD + FAR only |
| Implementation takes too long | Prioritize BGL + one detector + S1–S6 |
| December experiments fail | Technical freeze before Christmas and reserve January for revision |

---

# 21. Minimum Viable Research Scope

If time becomes constrained, the project must still complete:

```text
BGL
 ↓
Log Parsing
 ↓
Temporal Windows
 ↓
1 Existing Anomaly Detector
 ↓
S1–S6 Semi-Synthetic Scenarios
 ↓
Drift Characterization
 ↓
Adapt / No-Adapt Policy
 ↓
Static vs Periodic vs Naive vs Proposed
 ↓
F1 + AD + FAR
```

The following are optional:

- Thunderbird
- Multiple anomaly detectors
- Advanced model-update strategies
- Natural-evolution analysis
- Large-scale Data Lake
- Production deployment

---

# 22. Project Timeline

Target:

> Complete all core experiments before 24 December 2026.

January 2027 is reserved for:

- report revision
- additional small experiments requested by advisor
- defense slides
- rehearsal

---

# 23. Milestone M0 — Scope Freeze

**Period:** 11–14 September 2026

## Input

- Current proposal
- Advisor feedback
- Research title
- RQ1–RQ3
- Scope decisions

## Tasks

- Finalize research scope
- Freeze drift types
- Freeze primary metrics
- Create repository
- Define project structure
- Define experiment naming convention

## Output

- Final proposal
- Final RQs
- Repository initialized
- Project README
- Initial experiment configuration structure

## Definition of Done

- No additional drift types are added.
- Metrics are fixed to F1, AD, FAR.
- BGL is confirmed as primary dataset.

---

# 24. Milestone M1 — Literature Foundation

**Period:** 15–27 September 2026

## Input

Key literature:

- Concept drift surveys
- ADWIN
- Drain
- DeepLog
- LogAnomaly
- EvLog
- Loghub
- Recent drift-aware LAD studies

## Tasks

Create a literature matrix containing:

```text
Paper
Year
Dataset
Representation
Detector
Drift type
Drift detection
Adaptation
Ground truth
Temporal evaluation
Metrics
Limitations
Potential gap
```

## Output

- 15–20 reviewed papers
- Literature matrix
- Research taxonomy
- Preliminary research-gap statement
- Related-work notes

## Definition of Done

You can answer:

1. What has already been done?
2. What is still weak or missing?
3. Why is the proposed adaptation policy necessary?

---

# 25. Milestone M2 — BGL Data Foundation

**Period:** 28 September – 5 October 2026

## Input

- Raw BGL dataset
- Parsing configuration
- Label definitions

## Tasks

- Load raw logs
- Parse timestamps
- Normalize labels
- Extract templates
- Maintain chronological ordering
- Produce event-level data
- Build template registry

## Output

```text
events.parquet
templates.parquet
dataset_stats.json
parsing_config.yaml
```

Minimum statistics:

- total logs
- normal/anomalous logs
- unique templates
- first/last timestamps
- template frequencies

## Definition of Done

The same pipeline can regenerate the processed BGL dataset from raw input.

---

# 26. Milestone M3 — Temporal EDA

**Period:** 6–12 October 2026

## Input

- `events.parquet`
- `templates.parquet`

## Tasks

Create temporal windows and analyze:

- template frequency over time
- new-template rate over time
- anomaly rate over time
- number of active templates
- distribution divergence
- entropy / distribution statistics if needed

## Output

```text
windows.parquet
eda.ipynb
figures/
eda_report.md
```

Required figures:

1. Template frequency × time
2. New-template rate × time
3. Anomaly ratio × time
4. Distribution change × time

## Definition of Done

You understand how BGL behaves temporally and can justify the windowing strategy.

---

# 27. Milestone M4 — Static Baseline

**Period:** 13–20 October 2026

## Input

- Processed BGL
- Chronological train/validation/test split
- One existing anomaly detector

## Tasks

- Train detector
- Produce anomaly predictions/scores
- Evaluate chronological baseline
- Store model/config/results

## Output

```text
baseline_model/
predictions.parquet
baseline_metrics.json
baseline_config.yaml
```

Required result:

- Baseline F1

## Definition of Done

One command can reproduce:

```text
BGL → detector → predictions → F1
```

---

# 28. Milestone M5 — Drift Generator V1

**Period:** 21–31 October 2026

## Input

- Processed BGL
- Template registry
- Normal templates
- Drift protocol

## Tasks

Implement S1–S6:

- S1 sudden frequency drift
- S2 gradual frequency drift
- S3 sudden template emergence
- S4 gradual template emergence
- S5 transient anomaly burst
- S6 no-drift control

Support:

- configurable magnitude
- configurable start/end
- configurable seed
- reproducible output

## Output

For each scenario:

```text
scenario_config.yaml
stream.parquet
ground_truth.json
manifest.json
```

## Definition of Done

Running the generator with the same config and random seed produces the same scenario.

---

# 29. GATE 1 — Experiment Foundation

**Deadline:** 31 October 2026

The following must work end-to-end:

```text
Raw BGL
 ↓
Processing
 ↓
Temporal windows
 ↓
Drift scenario
 ↓
Ground truth
 ↓
Anomaly detector
 ↓
Predictions
```

## Required evidence

- One command / pipeline can reproduce a complete scenario.
- Ground truth is produced before the proposed policy.
- No temporal leakage.

## If Gate 1 fails

Immediately cut:

- HDFS experiments
- Thunderbird
- Multiple detectors
- Data Lake enhancements

Focus only on BGL.

---

# 30. Milestone M6 — Drift Characterization V1

**Period:** 1–10 November 2026

## Input

- S1–S6 generated streams
- Temporal windows
- Ground-truth drift intervals

## Tasks

Implement features:

- new-template rate
- template-frequency distribution
- distribution divergence
- drift magnitude
- persistence

## Output

```text
drift_features.parquet
characterization_config.yaml
characterization_figures/
```

Each window should contain a drift-characterization vector.

## Definition of Done

Known drift regions show measurable changes in characterization signals.

---

# 31. Milestone M7 — Characterization Validation

**Period:** 11–17 November 2026

## Input

- Drift-characterization features
- Ground-truth scenarios S1–S6

## Tasks

Check whether characterization behaves as expected for:

- sudden drift
- gradual drift
- frequency drift
- template emergence
- transient anomaly
- no-drift control

## Output

- Characterization comparison tables
- Plots for S1–S6
- Threshold/persistence candidates
- Failure-case notes

## Definition of Done

You can explain which signals distinguish:

```text
persistent drift
vs
transient anomaly
vs
no drift
```

---

# 32. Milestone M8 — Adaptation Policy V1

**Period:** 18–30 November 2026

## Input

- Drift-characterization features
- Detector anomaly evidence
- Validation scenarios

## Tasks

Define policy inputs and decision rule.

Example conceptual structure:

```text
drift magnitude
+
persistence
+
new-template rate
+
distribution divergence
+
anomaly evidence
      ↓
Adapt / Do not adapt
```

Tune policy only on validation scenarios.

## Output

```text
adaptation_policy.py
policy_config.yaml
adaptation_events.parquet
```

Each adaptation event should contain:

```text
window_id
decision
decision_score
reason/features
action
```

## Definition of Done

Policy runs end-to-end on S1–S6 without accessing ground-truth labels during inference.

---

# 33. GATE 2 — Research Contribution Running

**Deadline:** 30 November 2026

The complete proposed pipeline must run:

```text
BGL
 ↓
Drift Scenario
 ↓
Existing Detector
 ↓
Drift Characterization
 ↓
Adaptation Policy
 ↓
Adapt / No Adapt
 ↓
Predictions
 ↓
F1 / AD / FAR
```

Results do not need to be optimal yet.

They only need to be technically valid and reproducible.

## If Gate 2 fails

Do not add complexity.

Reduce the policy to an interpretable rule-based/data-driven policy and finish the experiment.

---

# 34. Milestone M9 — Baseline Comparison

**Period:** 1–7 December 2026

## Input

- Final scenario protocol
- Static detector
- Proposed policy

## Implement comparison methods

1. Static
2. Periodic retraining
3. Naive drift-triggered adaptation
4. Proposed drift-aware adaptation policy

## Output

A common experiment runner producing:

```text
method
scenario
seed
F1
AD
FAR
```

## Definition of Done

All four methods run under the same:

- data
- detector
- scenarios
- seeds
- evaluation protocol

---

# 35. Milestone M10 — Main Experiments

**Period:** 8–17 December 2026

## Input

- Frozen experiment configs
- Frozen test scenarios
- Frozen test seeds

## Tasks

Run:

- S1–S6
- multiple drift magnitudes
- multiple random seeds
- all four comparison methods

## Output

```text
results_raw.parquet
experiment_manifest.json
run_logs/
```

Each run must store:

```text
scenario_id
method
seed
drift_magnitude
window_size
F1
AD
FAR
```

## Definition of Done

All required runs complete without tuning on test results.

---

# 36. Milestone M11 — Result Analysis

**Period:** 18–24 December 2026

## Input

- Raw experiment results

## Tasks

Calculate:

- mean
- standard deviation
- per-scenario performance
- per-drift-type performance
- failure cases

## Required analysis

### F1

Does adaptation preserve anomaly-detection performance?

### AD

Does the policy adapt quickly enough?

### FAR

Does the policy avoid unnecessary adaptation?

## Output

```text
final_results.csv
tables/
figures/
analysis.md
```

## Definition of Done

Every RQ has at least one table or figure that directly supports its answer.

---

# 37. GATE 3 — Technical Freeze

**Deadline:** 24 December 2026

After this date:

## Allowed

- Bug fixes
- Re-running failed experiments
- Advisor-requested small experiments
- Visualization improvements
- Writing

## Not allowed unless advisor explicitly requests

- New drift type
- New primary metric
- New dataset
- New model family
- New major policy architecture

---

# 38. Milestone M12 — Complete Draft

**Period:** 25–31 December 2026

## Input

- Literature review
- Final methodology
- Final experiment protocol
- Final results

## Tasks

Write:

1. Introduction
2. Related Work
3. Problem Formulation
4. Methodology
5. Dataset and Experimental Setup
6. Results
7. Discussion
8. Limitations
9. Conclusion

## Output

- Full report draft
- All figures/tables numbered
- References complete

## Definition of Done

The advisor can read the report from beginning to end without needing missing experiment sections.

---

# 39. Milestone M13 — Revision

**Period:** 1–7 January 2027

## Input

- Advisor feedback
- Full report draft

## Tasks

- Fix methodology wording
- Clarify contribution
- Update figures
- Correct citations
- Run only necessary follow-up experiments

## Output

- Near-final report
- Final result tables
- Final appendix/config documentation

---

# 40. Milestone M14 — Defense Preparation

**Period:** 8 January 2027 onward

## Input

- Final report
- Final figures
- Final results

## Tasks

Prepare:

- defense slides
- 10–15 minute research story
- architecture diagram
- experiment diagram
- main results
- limitations
- Q&A notes
- demo only if useful

## Output

```text
defense_slides.pptx
defense_script.md
qa_notes.md
```

## Definition of Done

You can explain the entire research in this chain:

```text
Problem
 ↓
Concept Drift
 ↓
Why Static LAD Fails
 ↓
Drift Characterization
 ↓
Adaptation Decision
 ↓
Controlled Evaluation
 ↓
F1 / AD / FAR
 ↓
Conclusion
```

---

# 41. Master Input → Output Map

```text
INPUT 1
Research Literature
    ↓
OUTPUT
Research gap + RQs + hypotheses


INPUT 2
Raw BGL Logs
    ↓
OUTPUT
Parsed chronological event dataset


INPUT 3
Processed Events
    ↓
OUTPUT
Temporal windows + template statistics


INPUT 4
Normal BGL Templates + Drift Config
    ↓
OUTPUT
S1–S6 semi-synthetic streams + ground truth


INPUT 5
Drift Streams
    ↓
OUTPUT
Drift-characterization features


INPUT 6
Drift Features + Anomaly Evidence
    ↓
OUTPUT
Adapt / No-Adapt decisions


INPUT 7
Adaptation Policy + Existing Detector
    ↓
OUTPUT
Updated predictions over time


INPUT 8
Predictions + Ground Truth
    ↓
OUTPUT
F1 + Adaptation Delay + False Adaptation Rate


INPUT 9
All Experiment Results
    ↓
OUTPUT
Tables + Figures + RQ Answers


INPUT 10
RQ Answers + Literature + Method
    ↓
OUTPUT
Final Graduation Project Report
```

---

# 42. Final Project Deliverables

By the reporting deadline, the project should contain:

## Research

- Final research proposal
- Literature matrix
- Related-work summary
- Defined RQs
- Defined hypotheses

## Data

- Raw-data reference
- Processed BGL dataset
- Template registry
- Temporal-window dataset
- Drift scenarios S1–S6
- Ground-truth manifests

## Code

- Preprocessing pipeline
- Parsing pipeline
- Baseline detector runner
- Drift generator
- Drift-characterization module
- Adaptation-policy module
- Evaluation module
- Experiment runner

## Experiment

- Static baseline
- Periodic retraining baseline
- Naive drift-triggered baseline
- Proposed policy
- Multiple-seed results

## Evaluation

- F1
- Adaptation Delay
- False Adaptation Rate

## Documentation

- Configuration files
- Random seeds
- Experiment manifests
- Reproduction instructions
- Final figures/tables

## Graduation Deliverables

- Final report
- Defense slides
- Q&A preparation
- Optional demo

---

# 43. Weekly Project Health Check

At the end of every week, answer:

### 1. What artifact did I produce?

Examples:

```text
events.parquet
scenario_config.yaml
drift_features.parquet
results_raw.parquet
```

### 2. Which research question does this artifact support?

Every implementation task should support RQ1, RQ2, or RQ3.

### 3. Is the result reproducible?

Can another run regenerate the same result from:

```text
code
+
config
+
data
+
random seed
```

If not, the milestone is not complete.

---

# 44. Critical Deadlines Summary

```text
14 Sep
Scope frozen

27 Sep
Literature foundation complete

05 Oct
BGL processed

12 Oct
Temporal EDA complete

20 Oct
Static baseline complete

31 Oct
GATE 1:
Data + drift generator + baseline end-to-end

10 Nov
Drift characterization V1

17 Nov
Characterization validated

30 Nov
GATE 2:
Proposed adaptation policy end-to-end

07 Dec
All comparison baselines ready

17 Dec
Main experiments complete

24 Dec
GATE 3:
Technical freeze

31 Dec
Full report draft

07 Jan
Near-final report

Jan
Defense preparation
```

---

# 45. Project Success Criteria

The core project is considered successful if it demonstrates that:

1. Template emergence and/or frequency drift reduce static detector performance.
2. The proposed characterization captures meaningful temporal drift information.
3. The adaptation policy can decide whether and when to adapt.
4. The proposed policy achieves a useful trade-off among:
   - high F1
   - low Adaptation Delay
   - low False Adaptation Rate
5. The full experiment is reproducible from fixed data, code, configs, and random seeds.

The project does **not** need to solve every form of concept drift or outperform every existing log-anomaly detector.

The central research contribution remains:

> **Drift Characterization + Drift-Aware Adaptation Decision under Concept Drift.**
