from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from adaptive_lad.adaptation.selection import select_adaptation_candidates
from adaptive_lad.detectors.base import Detector
from adaptive_lad.detectors.factory import build_detector
from adaptive_lad.drift.characterization import DriftCharacterizer
from adaptive_lad.evaluation.metrics import evaluate_run
from adaptive_lad.policies.strategies import build_policy


@dataclass(frozen=True)
class RunResult:
    predictions: pd.DataFrame
    drift_features: pd.DataFrame
    adaptation_events: pd.DataFrame
    metrics: dict[str, Any]


def run_experiment(
    events: pd.DataFrame,
    ground_truth: dict[str, Any],
    *,
    method: str,
    warmup_windows: int,
    detector_config: dict[str, Any],
    characterization_config: dict[str, Any],
    policy_config: dict[str, Any],
    evaluation_window_ids: list[int] | None = None,
    prefitted_detector: Detector | None = None,
    characterization_reference_window_ids: list[int] | None = None,
) -> RunResult:
    window_ids = sorted(int(value) for value in events["window_id"].unique())
    if warmup_windows <= 0 or warmup_windows >= len(window_ids):
        raise ValueError("warmup_windows must leave at least one evaluation window")
    training_ids = window_ids[:warmup_windows]
    evaluation_ids = (
        window_ids[warmup_windows:]
        if evaluation_window_ids is None
        else sorted({int(value) for value in evaluation_window_ids})
    )
    if not evaluation_ids or not set(evaluation_ids).issubset(window_ids):
        raise ValueError("Evaluation windows must be a non-empty subset of the event stream")
    if set(training_ids) & set(evaluation_ids) or min(evaluation_ids) <= max(training_ids):
        raise ValueError("Evaluation windows must occur strictly after warm-up windows")
    training = events[events["window_id"].isin(training_ids)].copy()

    detector = prefitted_detector or build_detector(detector_config)
    if prefitted_detector is None:
        detector.fit(training)
    characterizer = DriftCharacterizer(
        reference_window_count=int(characterization_config["reference_window_count"]),
        minimum_reference_events=int(characterization_config["minimum_reference_events"]),
        divergence_threshold=float(characterization_config["divergence_threshold"]),
        new_template_rate_threshold=float(characterization_config["new_template_rate_threshold"]),
        magnitude_weights=dict(characterization_config["magnitude_weights"]),
        persistence_signal_threshold=float(characterization_config["persistence_signal_threshold"]),
    )

    # Labels are allowed only for the offline semi-supervised fit/reference phase.
    # Evaluation-time characterization and adaptation never receive ground truth.
    reference_training = training
    if "anomaly_label" in training.columns:
        labeled_normal = training[training["anomaly_label"] == 0]
        if not labeled_normal.empty:
            reference_training = labeled_normal
    characterizer.mark_seen(reference_training)
    reference_ids = characterization_reference_window_ids or training_ids
    if not set(reference_ids).issubset(training_ids):
        raise ValueError("Characterization reference windows must be warm-up windows")
    for window_id in reference_ids:
        window = reference_training[reference_training["window_id"] == window_id]
        if window.empty:
            continue
        # Warm-up anomaly evidence is discarded; zero scores avoid redundant model
        # inference while retaining the exact template reference and seen set.
        characterizer.update(window, np.zeros(len(window), dtype=float))
    characterizer.freeze_reference()

    policy = build_policy(method, policy_config, first_evaluation_window=evaluation_ids[0])
    buffer_size = int(policy_config.get("adaptation_buffer_windows", 3))
    adaptation_buffer: deque[pd.DataFrame] = deque(maxlen=buffer_size)
    reference_templates = {str(value) for value in reference_training["template_id"]}
    prediction_rows: list[pd.DataFrame] = []
    feature_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, object]] = []

    for window_id in evaluation_ids:
        window = events[events["window_id"] == window_id].copy()
        scores = detector.score(window)
        normalized_scores = detector.normalized_score(window)
        predictions = detector.predict(window)
        audit = window[["event_uid", "window_id", "anomaly_label", "template_id"]].copy()
        audit["anomaly_score"] = scores
        audit["prediction"] = predictions
        prediction_rows.append(audit)

        features = characterizer.update(window, normalized_scores)
        feature_rows.append(features.to_dict())
        decision = policy.decide(features)
        buffered_window = window.drop(
            columns=["anomaly_label", "drift_label"], errors="ignore"
        ).copy()
        buffered_window["_normalized_anomaly_score"] = normalized_scores
        buffered_window["_prediction"] = predictions
        buffered_window["_novel_to_reference"] = ~buffered_window["template_id"].astype(str).isin(
            reference_templates
        )
        adaptation_buffer.append(buffered_window)
        decision_row = decision.to_dict()
        decision_row.update(
            {
                "adaptation_observed_count": 0,
                "adaptation_selected_count": 0,
                "adaptation_rejected_count": 0,
                "recurrent_template_count": 0,
                "recurrent_novel_template_count": 0,
            }
        )
        if decision.decision:
            selection = select_adaptation_candidates(
                pd.concat(list(adaptation_buffer), ignore_index=True),
                maximum_normalized_score=float(
                    policy_config.get("adaptation_maximum_normalized_score", 0.8)
                ),
                minimum_recurrent_template_windows=int(
                    policy_config.get("adaptation_minimum_recurrent_template_windows", 2)
                ),
                minimum_recurrent_template_events=int(
                    policy_config.get("adaptation_minimum_recurrent_template_events", 3)
                ),
            )
            decision_row.update(
                {
                    "adaptation_observed_count": selection.observed_count,
                    "adaptation_selected_count": selection.selected_count,
                    "adaptation_rejected_count": selection.rejected_count,
                    "recurrent_template_count": selection.recurrent_template_count,
                    "recurrent_novel_template_count": selection.recurrent_novel_template_count,
                }
            )
            if not selection.events.empty:
                detector.update(selection.events)
                characterizer.rebase(selection.events)
                reference_templates.update(str(value) for value in selection.events["template_id"])
            else:
                decision_row["action"] = "skipped_empty_update"
        decision_rows.append(decision_row)

    predictions_frame = pd.concat(prediction_rows, ignore_index=True)
    features_frame = pd.DataFrame(feature_rows)
    decisions_frame = pd.DataFrame(decision_rows)
    metrics = evaluate_run(
        predictions_frame,
        decisions_frame,
        ground_truth,
        evaluation_windows=evaluation_ids,
    )
    return RunResult(
        predictions=predictions_frame,
        drift_features=features_frame,
        adaptation_events=decisions_frame,
        metrics=metrics,
    )
