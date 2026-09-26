from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd


class TemplateFrequencyDetector:
    """Interpretable existing detector baseline based on template surprisal.

    It intentionally remains simple: the thesis contribution is the adaptation policy,
    not a new anomaly detector. Replace this class behind the Detector protocol for
    DeepLog/LogAnomaly experiments.
    """

    def __init__(
        self,
        *,
        alpha: float = 1.0,
        threshold_quantile: float = 0.95,
        minimum_probability: float = 1e-9,
        recalibrate_threshold_on_update: bool = True,
        threshold_update_rate: float = 1.0,
    ) -> None:
        if alpha <= 0 or not 0 < threshold_quantile < 1 or not 0 <= threshold_update_rate <= 1:
            raise ValueError("Invalid detector parameters")
        self.alpha = alpha
        self.threshold_quantile = threshold_quantile
        self.minimum_probability = minimum_probability
        self.recalibrate_threshold_on_update = recalibrate_threshold_on_update
        self.threshold_update_rate = threshold_update_rate
        self.counts: Counter[str] = Counter()
        self.total = 0
        self.threshold = float("inf")

    def fit(self, events: pd.DataFrame) -> None:
        training = events
        if "anomaly_label" in events.columns:
            normal = events[events["anomaly_label"] == 0]
            if not normal.empty:
                training = normal
        self.counts = Counter(str(value) for value in training["template_id"])
        self.total = sum(self.counts.values())
        if self.total == 0:
            raise ValueError("Cannot fit a detector on empty data")
        training_scores = self.score(training)
        self.threshold = float(np.quantile(training_scores, self.threshold_quantile))

    def score(self, events: pd.DataFrame) -> np.ndarray:
        if self.total == 0:
            raise RuntimeError("Detector must be fitted before scoring")
        vocabulary = max(len(self.counts), 1)
        denominator = self.total + self.alpha * (vocabulary + 1)
        probabilities = np.array(
            [
                max(
                    (self.counts.get(str(template), 0) + self.alpha) / denominator,
                    self.minimum_probability,
                )
                for template in events["template_id"]
            ],
            dtype=float,
        )
        return -np.log(probabilities)

    def normalized_score(self, events: pd.DataFrame) -> np.ndarray:
        raw = self.score(events)
        scale = max(self.threshold, 1e-12)
        return np.clip(raw / scale, 0.0, 1.0)

    def predict(self, events: pd.DataFrame) -> np.ndarray:
        return (self.score(events) > self.threshold + 1e-12).astype(np.int8)

    def update(self, events: pd.DataFrame) -> None:
        if events.empty:
            return
        # Inference-time adaptation has no label access: selected events are pseudo-normal.
        self.counts.update(str(value) for value in events["template_id"])
        self.total = sum(self.counts.values())
        if self.recalibrate_threshold_on_update:
            updated_threshold = float(np.quantile(self.score(events), self.threshold_quantile))
            self.threshold = (
                1 - self.threshold_update_rate
            ) * self.threshold + self.threshold_update_rate * updated_threshold
