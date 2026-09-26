from pathlib import Path

from adaptive_lad.cli import validate_configs
from adaptive_lad.config import ScenarioConfig


def test_all_repository_configs_are_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate_configs(root / "configs") >= 10


def test_no_drift_config_has_no_interval() -> None:
    config = ScenarioConfig.from_mapping(
        {
            "scenario_id": "S6",
            "drift_type": "none",
            "temporal_pattern": "none",
            "start_window": None,
            "end_window": None,
            "drift_magnitude": 0,
            "affected_templates": [],
            "window_size": 10,
            "random_seed": 1,
        }
    )
    assert config.start_window is None
