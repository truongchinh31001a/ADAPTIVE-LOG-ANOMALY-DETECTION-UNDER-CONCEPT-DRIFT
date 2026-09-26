from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_INTERNAL_COLUMNS = {
    "_normalized_anomaly_score",
    "_prediction",
    "_novel_to_reference",
}
_GROUND_TRUTH_COLUMNS = {"anomaly_label", "drift_label"}


@dataclass(frozen=True)
class AdaptationSelection:
    events: pd.DataFrame
    observed_count: int
    selected_count: int
    rejected_count: int
    recurrent_template_count: int
    recurrent_novel_template_count: int


def select_adaptation_candidates(
    buffered_events: pd.DataFrame,
    *,
    maximum_normalized_score: float,
    minimum_recurrent_template_windows: int,
    minimum_recurrent_template_events: int,
) -> AdaptationSelection:
    """Select pseudo-normal events without consulting inference-time labels.

    Low-risk events must be predicted normal and remain below the configured score
    ceiling. High-score events may also be selected when their template recurs across
    enough windows and events. The latter rule supports persistent frequency shifts
    and template emergence; the policy's persistence/transient guard opens this gate.
    """
    if not 0 <= maximum_normalized_score <= 1:
        raise ValueError("maximum_normalized_score must be in [0, 1]")
    if minimum_recurrent_template_windows <= 0 or minimum_recurrent_template_events <= 0:
        raise ValueError("template recurrence thresholds must be positive")
    required = _INTERNAL_COLUMNS | {"template_id", "window_id"}
    missing = required - set(buffered_events.columns)
    if missing:
        raise ValueError(f"Adaptation buffer is missing columns: {sorted(missing)}")

    observed_count = len(buffered_events)
    if buffered_events.empty:
        return AdaptationSelection(
            events=buffered_events.drop(
                columns=list(_INTERNAL_COLUMNS | _GROUND_TRUTH_COLUMNS), errors="ignore"
            ),
            observed_count=0,
            selected_count=0,
            rejected_count=0,
            recurrent_template_count=0,
            recurrent_novel_template_count=0,
        )

    low_risk = (buffered_events["_prediction"].astype(int) == 0) & (
        buffered_events["_normalized_anomaly_score"].astype(float) <= maximum_normalized_score
    )
    recurrence = buffered_events.groupby("template_id").agg(
        window_count=("window_id", "nunique"),
        event_count=("template_id", "size"),
    )
    recurrent_templates = {
        str(template_id)
        for template_id, row in recurrence.iterrows()
        if int(row["window_count"]) >= minimum_recurrent_template_windows
        and int(row["event_count"]) >= minimum_recurrent_template_events
    }
    recurrent = buffered_events["template_id"].astype(str).isin(recurrent_templates)
    novel_templates = set(
        buffered_events.loc[
            buffered_events["_novel_to_reference"].astype(bool), "template_id"
        ].astype(str)
    )
    # Recurrence is evaluated only after a policy opens the adaptation gate. It
    # admits persistent high-score transitions needed for frequency drift as well
    # as persistent novel templates; one-window spikes remain excluded.
    selected = buffered_events.loc[low_risk | recurrent].copy()
    selected = selected.drop(
        columns=list(_INTERNAL_COLUMNS | _GROUND_TRUTH_COLUMNS), errors="ignore"
    )
    return AdaptationSelection(
        events=selected,
        observed_count=observed_count,
        selected_count=len(selected),
        rejected_count=observed_count - len(selected),
        recurrent_template_count=len(recurrent_templates),
        recurrent_novel_template_count=len(recurrent_templates & novel_templates),
    )
