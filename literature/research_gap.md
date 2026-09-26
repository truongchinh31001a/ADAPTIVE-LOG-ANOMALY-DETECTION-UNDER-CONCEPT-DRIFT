# Research gap and positioning

Updated: 24 September 2026.

## Terminology decision

The thesis should not treat every change in template frequency as real concept drift.
The strict supervised definition in Gama et al. (2014) centers on a change in the
relationship between inputs and the target, while a change in the marginal log-event
distribution can be virtual drift or covariate shift. The operational term used in the
method and experiments will therefore be **observable log-distribution drift**. The
proposal title may retain “concept drift”, but the thesis must state that template
frequency drift and template emergence are observable drift mechanisms that can degrade
the anomaly detector; the experiments test that degradation rather than assuming that
every injected change alters `P(Y|X)`.

Primary terminology source: https://doi.org/10.1145/2523813

## What prior work already covers

1. DeepLog, LogAnomaly, LogBERT, HitAnomaly, LogEncoder, and LogSD mainly improve the
   underlying anomaly detector or representation.
2. LogRobust, RT-Log, and EvLog improve robustness to unseen templates, unstable logs,
   distribution shift, or software-version evolution without making a detector-neutral
   whether-and-when update decision the main object of evaluation.
3. LogOnline continuously learns normal sequence patterns online. OMLog detects a
   distribution gap with MMD and combines it with online meta-learning.
4. IDLLog (2026) is the closest published work: it triggers incremental fine-tuning when
   the proportion of changed templates exceeds a threshold and preserves historical
   knowledge through herding or knowledge distillation.

The thesis must therefore not claim to be the first adaptive or online log anomaly
detector. That claim is contradicted by LogOnline, OMLog, and IDLLog.

Closest-work sources:

- LogOnline: https://doi.org/10.1109/ASE56229.2023.00043
- EvLog: https://arxiv.org/abs/2306.01509
- OMLog: https://arxiv.org/abs/2410.16612
- IDLLog: https://doi.org/10.1016/j.infsof.2026.108199

## Defensible research gap

Existing evolving-log approaches predominantly pursue one of three strategies:
robust representation without explicit adaptation, continuous online updating, or an
update trigger based on a single distribution signal. There is still limited controlled
evidence about a **detector-agnostic adaptation decision layer** that:

1. characterizes both template emergence and template-frequency drift using type,
   magnitude, persistence, and detector anomaly evidence;
2. explicitly decides **whether** adaptation is warranted and **when** it should occur;
3. can reject transient anomaly bursts and no-drift periods rather than treating every
   distribution alarm as evidence to update;
4. is evaluated on the same frozen streams against static, periodic, and naive-triggered
   baselines; and
5. measures policy behavior through Adaptation Delay and False Adaptation Rate together
   with downstream anomaly-detection F1.

This is a deliberately narrower claim than “adaptive LAD is new”. It positions the
scientific contribution in the decision and evaluation protocol, not in inventing a new
detector or a more complex update operator.

## Final bounded novelty statement

> This study evaluates a detector-agnostic, drift-aware decision policy that uses
> multi-signal characterization of observable log-distribution drift to decide whether
> and when an existing log anomaly detector should adapt. Unlike always-online,
> periodic, or single-alarm update strategies, the policy is explicitly evaluated for
> delayed, missed, and false adaptations under persistent drift, transient anomaly, and
> no-drift controls.

The words “first” and “state of the art” are intentionally not used. The contribution is
the controlled decision/evaluation protocol and the demonstrated safety--latency
trade-off, not the existence of conditional or online adaptation itself.

## Closest-work audit and evidence boundary

- The official LogOnline record describes continuous label-free learning of normal
  sequence patterns. OMLog's full text characterizes LogOnline as selecting
  high-confidence normal samples and updating before each detection. Neither reviewed
  source defines AD/FAR or S5/S6-style policy controls.
- OMLog uses MMD to condition online meta-learning versus offline inference. Its full
  evaluation reports precision/recall/F1, runtime, five independent runs, ablations,
  and threshold sensitivity on stable HDFS/evolved BGL. Searches of the paper found no
  Adaptation Delay, False Adaptation Rate, or explicit transient/no-drift update test.
- The official IDLLog article describes partial fine-tuning triggered when changed
  templates exceed a predefined proportion, with herding or knowledge distillation.
  Its public article text reports detection effectiveness/efficiency rather than the
  timing and false-action metrics used here.

This is an evidence-bounded absence claim: it says those metrics/controls were not found
in the reviewed versions, not that no related study can contain them. Any later version
or newly published closest work must be re-audited before thesis submission.
