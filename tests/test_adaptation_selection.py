import pandas as pd

from adaptive_lad.adaptation.selection import select_adaptation_candidates


def test_selection_keeps_low_risk_and_recurrent_novel_events_without_labels() -> None:
    buffered = pd.DataFrame(
        {
            "event_uid": ["n1", "a1", "e1", "e2", "s1"],
            "window_id": [10, 10, 10, 11, 11],
            "template_id": ["KNOWN", "KNOWN_ANOM", "EMERGED", "EMERGED", "SPIKE"],
            "anomaly_label": [0, 1, 0, 0, 1],
            "drift_label": ["emergence"] * 5,
            "_normalized_anomaly_score": [0.2, 1.0, 1.0, 1.0, 1.0],
            "_prediction": [0, 1, 1, 1, 1],
            "_novel_to_reference": [False, False, True, True, True],
        }
    )

    result = select_adaptation_candidates(
        buffered,
        maximum_normalized_score=0.8,
        minimum_recurrent_template_windows=2,
        minimum_recurrent_template_events=2,
    )

    assert set(result.events["event_uid"]) == {"n1", "e1", "e2"}
    assert result.selected_count == 3
    assert result.rejected_count == 2
    assert result.recurrent_template_count == 1
    assert result.recurrent_novel_template_count == 1
    assert "anomaly_label" not in result.events
    assert "drift_label" not in result.events
    assert not any(column.startswith("_") for column in result.events)


def test_selection_rejects_single_window_novel_spike() -> None:
    buffered = pd.DataFrame(
        {
            "event_uid": ["s1", "s2", "s3"],
            "window_id": [10, 10, 10],
            "template_id": ["SPIKE"] * 3,
            "_normalized_anomaly_score": [1.0] * 3,
            "_prediction": [1] * 3,
            "_novel_to_reference": [True] * 3,
        }
    )

    result = select_adaptation_candidates(
        buffered,
        maximum_normalized_score=0.8,
        minimum_recurrent_template_windows=2,
        minimum_recurrent_template_events=2,
    )

    assert result.events.empty
    assert result.selected_count == 0
    assert result.rejected_count == 3


def test_selection_allows_recurrent_high_risk_frequency_shift() -> None:
    buffered = pd.DataFrame(
        {
            "event_uid": ["a1", "a2"],
            "window_id": [10, 11],
            "template_id": ["KNOWN_ANOMALY", "KNOWN_ANOMALY"],
            "_normalized_anomaly_score": [1.0, 1.0],
            "_prediction": [1, 1],
            "_novel_to_reference": [False, False],
        }
    )

    result = select_adaptation_candidates(
        buffered,
        maximum_normalized_score=0.8,
        minimum_recurrent_template_windows=2,
        minimum_recurrent_template_events=2,
    )

    assert set(result.events["event_uid"]) == {"a1", "a2"}
