# Data contracts

## Event-level table

Required columns:

| Column | Type | Meaning |
|---|---|---|
| `event_uid` | string | stable unique event identifier |
| `timestamp` | datetime64[ns, UTC] | chronological event time |
| `dataset` | string | source dataset |
| `host` | string | emitting node/host, possibly empty |
| `component` | string | component, possibly empty |
| `raw_message` | string | unmodified message text |
| `parsed_message` | string | normalized message/template text |
| `template_id` | string | deterministic template identifier |
| `parameters` | string | JSON array of extracted values |
| `anomaly_label` | int8 | 1 anomaly, 0 normal |
| `window_id` | int64 | monotonically increasing temporal window |
| `split` | string | train, validation, or test |

Generated scenario streams add `scenario_id`, `drift_label`, and `source_event_uid`.

## Window-level drift feature table

`window_id`, `start_time`, `end_time`, `num_events`, `num_templates`,
`num_new_templates`, `new_template_rate`, `template_frequency_vector` (JSON),
`distribution_divergence`, `drift_magnitude`, `persistence`, `anomaly_ratio`, and
`anomaly_evidence`.

## Adaptation event table

`window_id`, `decision`, `decision_score`, `reason`, `action`, `method`,
`adaptation_observed_count`, `adaptation_selected_count`,
`adaptation_rejected_count`, `recurrent_template_count`, and
`recurrent_novel_template_count`.
The table must be an inference audit trail and therefore must not contain ground-truth
drift labels as policy inputs.

## Ground truth

Ground truth is a separate JSON object containing scenario metadata, drift intervals,
valid adaptation intervals, invalid regions, seed, and stream checksum. It is joined
only during evaluation.
