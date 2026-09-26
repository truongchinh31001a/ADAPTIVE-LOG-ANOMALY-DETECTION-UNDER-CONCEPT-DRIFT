import pandas as pd

from adaptive_lad.detectors.template_frequency import TemplateFrequencyDetector


def test_update_recalibrates_threshold_from_selected_pseudo_normal_events() -> None:
    training = pd.DataFrame(
        {
            "template_id": ["A"] * 90 + ["B"] * 10,
            "anomaly_label": [0] * 100,
        }
    )
    update = pd.DataFrame({"template_id": ["B"] * 80 + ["A"] * 20})
    detector = TemplateFrequencyDetector(
        threshold_quantile=0.95,
        recalibrate_threshold_on_update=True,
        threshold_update_rate=1.0,
    )
    detector.fit(training)
    old_threshold = detector.threshold

    detector.update(update)

    assert detector.threshold != old_threshold
    assert detector.predict(update).mean() <= 0.05


def test_update_can_keep_frozen_threshold_for_ablation() -> None:
    training = pd.DataFrame(
        {
            "template_id": ["A"] * 90 + ["B"] * 10,
            "anomaly_label": [0] * 100,
        }
    )
    detector = TemplateFrequencyDetector(recalibrate_threshold_on_update=False)
    detector.fit(training)
    old_threshold = detector.threshold

    detector.update(pd.DataFrame({"template_id": ["B"] * 100}))

    assert detector.threshold == old_threshold
