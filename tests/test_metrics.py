import pandas as pd

from adaptive_lad.evaluation.metrics import evaluate_run


def test_adaptation_delay_and_far() -> None:
    predictions = pd.DataFrame(
        {
            "window_id": [5, 7, 9],
            "anomaly_label": [0, 1, 1],
            "prediction": [0, 1, 0],
        }
    )
    decisions = pd.DataFrame(
        {
            "window_id": [5, 6, 7, 8, 9, 10],
            "decision": [False, False, True, False, False, True],
        }
    )
    ground_truth = {
        "episodes": [
            {
                "drift_start": 6,
                "drift_end": 8,
                "valid_adaptation_start": 6,
                "valid_adaptation_end": 8,
            }
        ]
    }
    metrics = evaluate_run(
        predictions, decisions, ground_truth, evaluation_windows=[5, 6, 7, 8, 9, 10]
    )
    assert metrics["adaptation_delay"] == 1
    assert metrics["missed_adaptations"] == 0
    assert metrics["false_adaptation_count"] == 1
    assert metrics["false_adaptation_rate"] == 1 / 3
    assert metrics["f1_post_adaptation"] == 0.0
    assert set(metrics) >= {"f1_pre_drift", "f1_during_drift", "f1_post_drift"}
