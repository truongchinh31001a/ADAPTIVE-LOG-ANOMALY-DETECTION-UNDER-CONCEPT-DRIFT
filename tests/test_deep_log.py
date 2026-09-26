import numpy as np
import pandas as pd

from adaptive_lad.detectors.deep_log import DeepLogDetector
from adaptive_lad.detectors.factory import build_detector


def _events(templates: list[str], *, anomaly: list[int] | None = None) -> pd.DataFrame:
    count = len(templates)
    return pd.DataFrame(
        {
            "event_uid": [f"e-{index}" for index in range(count)],
            "timestamp": pd.date_range("2026-01-01", periods=count, freq="s", tz="UTC"),
            "host": ["node-1"] * count,
            "template_id": templates,
            "anomaly_label": anomaly or [0] * count,
        }
    )


def test_deep_log_scores_unknown_template_and_can_update() -> None:
    detector = DeepLogDetector(
        sequence_length=3,
        embedding_dim=4,
        hidden_size=8,
        top_k=2,
        epochs=2,
        update_epochs=1,
        batch_size=8,
        max_training_sequences=100,
        replay_events=100,
        random_seed=7,
    )
    detector.fit(_events(["A", "B"] * 20))
    evaluation = _events(["A", "B", "NEW"])

    scores = detector.score(evaluation)
    predictions = detector.predict(evaluation)
    normalized = detector.normalized_score(evaluation)

    assert scores.shape == predictions.shape == normalized.shape == (3,)
    assert np.isfinite(scores).all()
    assert predictions[-1] == 1
    assert normalized[-1] == 1.0

    detector.update(evaluation.drop(columns="anomaly_label"))
    assert "NEW" in detector.template_to_index
    assert detector.training_summary is not None


def test_deep_log_fit_filters_labelled_anomaly_template() -> None:
    detector = DeepLogDetector(
        sequence_length=2,
        embedding_dim=4,
        hidden_size=8,
        epochs=1,
        update_epochs=1,
        batch_size=8,
        max_training_sequences=100,
        replay_events=100,
    )
    detector.fit(_events(["NORMAL", "ANOMALY"], anomaly=[0, 1]))

    assert set(detector.template_to_index) == {"NORMAL"}


def test_detector_factory_rejects_unknown_kind() -> None:
    try:
        build_detector({"kind": "not-a-detector"})
    except ValueError as error:
        assert "Unsupported detector kind" in str(error)
    else:
        raise AssertionError("Expected unsupported detector kind to fail")
