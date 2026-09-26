from __future__ import annotations

from typing import Any

from adaptive_lad.detectors.base import Detector
from adaptive_lad.detectors.deep_log import DeepLogDetector
from adaptive_lad.detectors.template_frequency import TemplateFrequencyDetector


def build_detector(config: dict[str, Any]) -> Detector:
    kind = str(config.get("kind", "template_frequency"))
    if kind == "template_frequency":
        return TemplateFrequencyDetector(
            alpha=float(config.get("alpha", 1.0)),
            threshold_quantile=float(config.get("threshold_quantile", 0.95)),
            minimum_probability=float(config.get("minimum_probability", 1e-9)),
            recalibrate_threshold_on_update=bool(
                config.get("recalibrate_threshold_on_update", True)
            ),
            threshold_update_rate=float(config.get("threshold_update_rate", 1.0)),
        )
    if kind == "deep_log":
        return DeepLogDetector(
            sequence_length=int(config.get("sequence_length", 10)),
            embedding_dim=int(config.get("embedding_dim", 32)),
            hidden_size=int(config.get("hidden_size", 64)),
            num_layers=int(config.get("num_layers", 1)),
            top_k=int(config.get("top_k", 9)),
            epochs=int(config.get("epochs", 5)),
            update_epochs=int(config.get("update_epochs", 1)),
            batch_size=int(config.get("batch_size", 512)),
            learning_rate=float(config.get("learning_rate", 1e-3)),
            max_training_sequences=int(config.get("max_training_sequences", 300_000)),
            replay_events=int(config.get("replay_events", 100_000)),
            score_quantile=float(config.get("score_quantile", 0.95)),
            random_seed=int(config.get("random_seed", 101)),
            device=str(config.get("device", "cpu")),
            torch_num_threads=int(config.get("torch_num_threads", 1)),
        )
    raise ValueError(f"Unsupported detector kind: {kind}")
