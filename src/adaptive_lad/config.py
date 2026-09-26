from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return value


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    drift_type: str
    temporal_pattern: str
    start_window: int | None
    end_window: int | None
    drift_magnitude: float
    affected_templates: tuple[str, ...]
    window_size: int
    random_seed: int
    tolerance_horizon: int = 3
    base_mode: str = "observed"
    evaluation_start_window: int | None = None
    evaluation_end_window: int | None = None
    reference_window_count: int = 10
    reference_min_templates: int = 1
    reference_min_dominant_templates: int = 1
    reference_min_template_fraction: float = 0.0
    background_anomaly_rate: float = 0.005

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ScenarioConfig:
        config = cls(
            scenario_id=str(value["scenario_id"]),
            drift_type=str(value["drift_type"]),
            temporal_pattern=str(value["temporal_pattern"]),
            start_window=_optional_int(value.get("start_window")),
            end_window=_optional_int(value.get("end_window")),
            drift_magnitude=float(value["drift_magnitude"]),
            affected_templates=tuple(str(x) for x in value.get("affected_templates", [])),
            window_size=int(value["window_size"]),
            random_seed=int(value["random_seed"]),
            tolerance_horizon=int(value.get("tolerance_horizon", 3)),
            base_mode=str(value.get("base_mode", "observed")),
            evaluation_start_window=_optional_int(value.get("evaluation_start_window")),
            evaluation_end_window=_optional_int(value.get("evaluation_end_window")),
            reference_window_count=int(value.get("reference_window_count", 10)),
            reference_min_templates=int(value.get("reference_min_templates", 1)),
            reference_min_dominant_templates=int(value.get("reference_min_dominant_templates", 1)),
            reference_min_template_fraction=float(
                value.get("reference_min_template_fraction", 0.0)
            ),
            background_anomaly_rate=float(value.get("background_anomaly_rate", 0.005)),
        )
        config.validate()
        return config

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScenarioConfig:
        return cls.from_mapping(load_yaml(path))

    def validate(self) -> None:
        allowed_types = {"frequency", "emergence", "transient_anomaly", "none"}
        allowed_patterns = {"sudden", "gradual", "none"}
        allowed_base_modes = {"observed", "stationary_replay"}
        if self.drift_type not in allowed_types:
            raise ValueError(f"Unsupported drift_type: {self.drift_type}")
        if self.temporal_pattern not in allowed_patterns:
            raise ValueError(f"Unsupported temporal_pattern: {self.temporal_pattern}")
        if self.base_mode not in allowed_base_modes:
            raise ValueError(f"Unsupported base_mode: {self.base_mode}")
        if not 0 <= self.drift_magnitude <= 1:
            raise ValueError("drift_magnitude must be in [0, 1]")
        if self.window_size <= 0 or self.tolerance_horizon < 0:
            raise ValueError("window_size must be positive and tolerance_horizon non-negative")
        if self.reference_window_count <= 0 or not 0 <= self.background_anomaly_rate < 1:
            raise ValueError("Invalid stationary replay parameters")
        if self.reference_min_templates <= 0 or self.reference_min_dominant_templates <= 0:
            raise ValueError("Reference template counts must be positive")
        if not 0 <= self.reference_min_template_fraction <= 1:
            raise ValueError("reference_min_template_fraction must be in [0, 1]")
        if self.base_mode == "stationary_replay" and self.evaluation_start_window is None:
            raise ValueError("stationary_replay requires evaluation_start_window")
        if (
            self.evaluation_end_window is not None
            and self.evaluation_start_window is not None
            and self.evaluation_end_window < self.evaluation_start_window
        ):
            raise ValueError("evaluation_end_window precedes evaluation_start_window")
        if self.drift_type == "none":
            if self.start_window is not None or self.end_window is not None:
                raise ValueError("No-drift scenarios must not define start/end windows")
            return
        if self.start_window is None or self.end_window is None:
            raise ValueError("Drift scenarios require start_window and end_window")
        if self.start_window < 0 or self.end_window < self.start_window:
            raise ValueError("Invalid drift window interval")
        if (
            self.drift_type in {"frequency", "emergence"}
            and self.temporal_pattern == "sudden"
            and self.start_window != self.end_window
        ):
            raise ValueError("Sudden drift must use the same start_window and end_window")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["affected_templates"] = list(self.affected_templates)
        return value


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
