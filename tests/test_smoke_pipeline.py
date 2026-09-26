from dataclasses import replace
from pathlib import Path

from adaptive_lad.config import ScenarioConfig, load_yaml
from adaptive_lad.data.bgl import make_demo_events
from adaptive_lad.drift.generator import generate_scenario
from adaptive_lad.experiments.runner import run_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_end_to_end_proposed_pipeline() -> None:
    events = make_demo_events(num_windows=15, window_size=50)
    scenario = replace(
        ScenarioConfig.from_yaml(ROOT / "configs/scenarios/s3_sudden_emergence.yaml"),
        window_size=50,
    )
    generated = generate_scenario(events, scenario)
    policy_config = load_yaml(ROOT / "configs/policy/default.yaml")
    policy_config["minimum_persistence"] = 2
    result = run_experiment(
        generated.events,
        generated.ground_truth,
        method="proposed",
        warmup_windows=5,
        detector_config=load_yaml(ROOT / "configs/detector/template_frequency.yaml"),
        characterization_config=load_yaml(ROOT / "configs/characterization/default.yaml"),
        policy_config=policy_config,
    )
    assert len(result.predictions) > 0
    assert len(result.drift_features) == 10
    assert set(result.metrics) >= {"f1", "adaptation_delay", "false_adaptation_rate"}
    assert "drift_label" not in result.adaptation_events.columns
    assert "adaptation_selected_count" in result.adaptation_events.columns
    adapted = result.adaptation_events[result.adaptation_events["decision"]]
    assert not adapted.empty
    assert (adapted["adaptation_selected_count"] > 0).all()


def test_offline_reference_excludes_labelled_training_anomalies() -> None:
    events = make_demo_events(seed=4, num_windows=3, window_size=10)
    events = events[~events["heldout_only"]].copy()
    warmup = events["window_id"] == 0
    events.loc[warmup, "template_id"] = "NORMAL"
    events.loc[warmup, "anomaly_label"] = 0
    anomalous_index = events.index[warmup][0]
    events.loc[anomalous_index, ["template_id", "anomaly_label"]] = ["TRAINING_ANOMALY", 1]
    evaluation_index = events.index[events["window_id"] == 1][0]
    events.loc[evaluation_index, ["template_id", "anomaly_label"]] = ["TRAINING_ANOMALY", 0]

    result = run_experiment(
        events,
        {"episodes": []},
        method="static",
        warmup_windows=1,
        detector_config=load_yaml(ROOT / "configs/detector/template_frequency.yaml"),
        characterization_config={
            "reference_window_count": 1,
            "minimum_reference_events": 1,
            "divergence_threshold": 0.1,
            "new_template_rate_threshold": 0.03,
            "magnitude_weights": {"divergence": 0.65, "new_template_rate": 0.35},
            "persistence_signal_threshold": 0.08,
        },
        policy_config=load_yaml(ROOT / "configs/policy/default.yaml"),
    )

    assert result.drift_features.iloc[0]["num_new_templates"] >= 1


def test_runner_restricts_evaluation_window_ids() -> None:
    events = make_demo_events(seed=9, num_windows=10, window_size=20)
    events = events[~events["heldout_only"]].copy()
    result = run_experiment(
        events,
        {"episodes": []},
        method="static",
        warmup_windows=3,
        detector_config=load_yaml(ROOT / "configs/detector/template_frequency.yaml"),
        characterization_config=load_yaml(ROOT / "configs/characterization/default.yaml"),
        policy_config=load_yaml(ROOT / "configs/policy/default.yaml"),
        evaluation_window_ids=[3, 4],
    )

    assert set(result.predictions["window_id"]) == {3, 4}
    assert set(result.drift_features["window_id"]) == {3, 4}
