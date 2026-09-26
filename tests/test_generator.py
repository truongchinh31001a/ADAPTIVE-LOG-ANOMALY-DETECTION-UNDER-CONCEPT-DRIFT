import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from adaptive_lad.config import ScenarioConfig
from adaptive_lad.data.bgl import make_demo_events
from adaptive_lad.drift.generator import generate_scenario
from adaptive_lad.io import frame_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_generation_is_deterministic() -> None:
    events = make_demo_events(num_windows=15, window_size=40)
    config = replace(
        ScenarioConfig.from_yaml(ROOT / "configs/scenarios/s1_sudden_frequency.yaml"),
        window_size=40,
    )
    first = generate_scenario(events, config)
    second = generate_scenario(events, config)
    assert frame_sha256(first.events) == frame_sha256(second.events)
    assert first.ground_truth["stream_sha256"] == second.ground_truth["stream_sha256"]


def test_frequency_generation_is_stable_across_python_hash_seeds() -> None:
    code = """
from dataclasses import replace
from pathlib import Path
from adaptive_lad.config import ScenarioConfig
from adaptive_lad.data.bgl import make_demo_events
from adaptive_lad.drift.generator import generate_scenario

root = Path.cwd()
events = make_demo_events(num_windows=15, window_size=40)
config = replace(
    ScenarioConfig.from_yaml(root / 'configs/scenarios/s1_sudden_frequency.yaml'),
    window_size=40,
)
print(generate_scenario(events, config).ground_truth['stream_sha256'])
"""
    hashes = []
    for hash_seed in ["1", "2"]:
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        hashes.append(
            subprocess.check_output(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                text=True,
            ).strip()
        )
    assert hashes[0] == hashes[1]


def test_emergence_uses_normal_heldout_templates() -> None:
    events = make_demo_events(num_windows=15, window_size=40)
    config = replace(
        ScenarioConfig.from_yaml(ROOT / "configs/scenarios/s3_sudden_emergence.yaml"),
        window_size=40,
    )
    generated = generate_scenario(events, config)
    before = generated.events[generated.events["window_id"] < config.start_window]
    after = generated.events[generated.events["window_id"] >= config.start_window]
    assert not before["template_id"].isin(config.affected_templates).any()
    emerged = after[after["template_id"].isin(config.affected_templates)]
    assert len(emerged) > 0
    assert (emerged["anomaly_label"] == 0).all()


def test_emergence_from_future_stream_preserves_window_sizes() -> None:
    events = make_demo_events(num_windows=15, window_size=40)
    events = events[~events["heldout_only"]].copy()
    future_index = events.index[events["window_id"] >= 12][:20]
    events.loc[future_index, "template_id"] = "FUTURE_NORMAL"
    config = replace(
        ScenarioConfig.from_yaml(ROOT / "configs/scenarios/s3_sudden_emergence.yaml"),
        window_size=40,
        affected_templates=("FUTURE_NORMAL",),
    )

    generated = generate_scenario(events, config)

    assert len(generated.events) == len(events)
    assert (generated.events.groupby("window_id").size() == 40).all()
    before = generated.events[generated.events["window_id"] < config.start_window]
    assert not before["template_id"].eq("FUTURE_NORMAL").any()


def test_negative_controls_never_require_adaptation() -> None:
    events = make_demo_events(num_windows=15, window_size=40)
    for filename in ["s5_transient_anomaly.yaml", "s6_no_drift.yaml"]:
        config = replace(
            ScenarioConfig.from_yaml(ROOT / "configs/scenarios" / filename), window_size=40
        )
        generated = generate_scenario(events, config)
        assert generated.ground_truth["requires_adaptation"] is False
        assert generated.ground_truth["episodes"] == []


def test_stationary_replay_has_fixed_background_anomaly_rate() -> None:
    events = make_demo_events(num_windows=10, window_size=40)
    events = events[~events["heldout_only"]].copy()
    events.loc[events["window_id"] < 3, "anomaly_label"] = 0
    events.loc[events.index[0], ["template_id", "anomaly_label"]] = ["A1", 1]
    config = replace(
        ScenarioConfig.from_yaml(ROOT / "configs/scenarios/s6_no_drift.yaml"),
        window_size=40,
        base_mode="stationary_replay",
        evaluation_start_window=3,
        evaluation_end_window=8,
        reference_window_count=2,
        background_anomaly_rate=0.05,
    )

    generated = generate_scenario(events, config)
    evaluation = generated.events[generated.events["window_id"].between(3, 8)]

    ratios = evaluation.groupby("window_id")["anomaly_label"].mean()
    assert (ratios == 0.05).all()
    assert generated.ground_truth["requires_adaptation"] is False
