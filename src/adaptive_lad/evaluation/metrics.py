from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score


def evaluate_run(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
    ground_truth: dict[str, Any],
    *,
    evaluation_windows: list[int],
) -> dict[str, Any]:
    if predictions.empty:
        raise ValueError("No predictions to evaluate")
    score = float(
        f1_score(
            predictions["anomaly_label"].astype(int),
            predictions["prediction"].astype(int),
            zero_division=0,
        )
    )
    phase_f1 = _f1_by_phase(predictions, ground_truth)
    adaptation_windows = sorted(
        int(value) for value in decisions.loc[decisions["decision"], "window_id"].tolist()
    )
    valid_windows: set[int] = set()
    delays: list[int] = []
    missed = 0
    for episode in ground_truth.get("episodes", []):
        start = int(episode["valid_adaptation_start"])
        end = int(episode["valid_adaptation_end"])
        valid_windows.update(range(start, end + 1))
        valid_actions = [window for window in adaptation_windows if start <= window <= end]
        if valid_actions:
            delays.append(valid_actions[0] - int(episode["drift_start"]))
        else:
            missed += 1
            delays.append(end - int(episode["drift_start"]))

    evaluation_set = set(evaluation_windows)
    invalid_windows = evaluation_set - valid_windows
    false_actions = [window for window in adaptation_windows if window in invalid_windows]
    far = len(false_actions) / len(invalid_windows) if invalid_windows else 0.0
    post_adaptation_f1 = _f1_post_adaptation(predictions, adaptation_windows, ground_truth)
    return {
        "f1": score,
        **phase_f1,
        "f1_post_adaptation": post_adaptation_f1,
        "adaptation_delay": float(np.mean(delays)) if delays else None,
        "missed_adaptations": missed,
        "false_adaptation_rate": float(far),
        "adaptation_count": len(adaptation_windows),
        "false_adaptation_count": len(false_actions),
        "evaluation_window_count": len(evaluation_set),
    }


def _f1_by_phase(
    predictions: pd.DataFrame, ground_truth: dict[str, Any]
) -> dict[str, float | None]:
    episodes = ground_truth.get("episodes", [])
    if not episodes:
        return {"f1_pre_drift": None, "f1_during_drift": None, "f1_post_drift": None}
    start = min(int(episode["drift_start"]) for episode in episodes)
    end = max(int(episode["drift_end"]) for episode in episodes)
    masks = {
        "f1_pre_drift": predictions["window_id"] < start,
        "f1_during_drift": predictions["window_id"].between(start, end),
        "f1_post_drift": predictions["window_id"] > end,
    }
    result: dict[str, float | None] = {}
    for name, mask in masks.items():
        subset = predictions.loc[mask]
        result[name] = (
            float(
                f1_score(
                    subset["anomaly_label"].astype(int),
                    subset["prediction"].astype(int),
                    zero_division=0,
                )
            )
            if not subset.empty
            else None
        )
    return result


def _f1_post_adaptation(
    predictions: pd.DataFrame,
    adaptation_windows: list[int],
    ground_truth: dict[str, Any],
) -> float | None:
    masks: list[pd.Series] = []
    for episode in ground_truth.get("episodes", []):
        start = int(episode["valid_adaptation_start"])
        end = int(episode["valid_adaptation_end"])
        valid_actions = [window for window in adaptation_windows if start <= window <= end]
        if valid_actions:
            masks.append(predictions["window_id"] > valid_actions[0])
    if not masks:
        return None
    combined = masks[0].copy()
    for mask in masks[1:]:
        combined |= mask
    subset = predictions.loc[combined]
    if subset.empty:
        return None
    return float(
        f1_score(
            subset["anomaly_label"].astype(int),
            subset["prediction"].astype(int),
            zero_division=0,
        )
    )
