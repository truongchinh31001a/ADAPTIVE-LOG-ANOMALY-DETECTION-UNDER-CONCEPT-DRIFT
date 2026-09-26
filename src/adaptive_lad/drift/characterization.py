from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DriftFeatures:
    window_id: int
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    num_events: int
    num_templates: int
    num_new_templates: int
    new_template_rate: float
    template_frequency_vector: str
    distribution_divergence: float
    drift_magnitude: float
    persistence: int
    anomaly_evidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DriftCharacterizer:
    def __init__(
        self,
        *,
        reference_window_count: int = 5,
        minimum_reference_events: int = 50,
        divergence_threshold: float = 0.10,
        new_template_rate_threshold: float = 0.03,
        magnitude_weights: dict[str, float] | None = None,
        persistence_signal_threshold: float = 0.08,
    ) -> None:
        if reference_window_count <= 0:
            raise ValueError("reference_window_count must be positive")
        self.reference_window_count = reference_window_count
        self.minimum_reference_events = minimum_reference_events
        self.divergence_threshold = divergence_threshold
        self.new_template_rate_threshold = new_template_rate_threshold
        self.weights = magnitude_weights or {"divergence": 0.65, "new_template_rate": 0.35}
        self.persistence_signal_threshold = persistence_signal_threshold
        self._history: deque[Counter[str]] = deque(maxlen=reference_window_count)
        self._frozen_reference: Counter[str] | None = None
        self._seen_templates: set[str] = set()
        self._persistence = 0

    def freeze_reference(self) -> None:
        """Freeze warm-up windows as the reference regime used during inference."""
        reference: Counter[str] = Counter()
        for prior_counts in self._history:
            reference.update(prior_counts)
        if sum(reference.values()) < self.minimum_reference_events:
            raise ValueError("Reference regime has fewer events than minimum_reference_events")
        self._frozen_reference = reference
        self._persistence = 0

    def mark_seen(self, events: pd.DataFrame) -> None:
        """Register offline-known templates without adding them to the drift reference."""
        self._seen_templates.update(str(value) for value in events["template_id"])

    def rebase(self, events: pd.DataFrame) -> None:
        """Set a new observable reference after an adaptation action."""
        if events.empty:
            return
        self._frozen_reference = Counter(str(value) for value in events["template_id"])
        self._seen_templates.update(self._frozen_reference)
        self._persistence = 0

    def update(self, window: pd.DataFrame, anomaly_scores: np.ndarray) -> DriftFeatures:
        if window.empty:
            raise ValueError("Cannot characterize an empty window")
        if len(anomaly_scores) != len(window):
            raise ValueError("anomaly_scores length must match the window")
        counts = Counter(str(value) for value in window["template_id"])
        new_templates = set(counts) - self._seen_templates
        new_template_events = sum(counts[template] for template in new_templates)
        new_template_rate = new_template_events / len(window)
        reference: Counter[str] = Counter()
        if self._frozen_reference is not None:
            reference.update(self._frozen_reference)
        else:
            for prior_counts in self._history:
                reference.update(prior_counts)
        divergence = jensen_shannon_divergence(reference, counts) if reference else 0.0
        magnitude = (
            self.weights["divergence"] * divergence
            + self.weights["new_template_rate"] * new_template_rate
        )
        signal = (
            magnitude >= self.persistence_signal_threshold
            or divergence >= self.divergence_threshold
            or new_template_rate >= self.new_template_rate_threshold
        )
        self._persistence = self._persistence + 1 if signal else 0
        vector = {key: value / len(window) for key, value in sorted(counts.items())}
        features = DriftFeatures(
            window_id=int(window["window_id"].iloc[0]),
            start_time=pd.to_datetime(window["timestamp"].min(), utc=True),
            end_time=pd.to_datetime(window["timestamp"].max(), utc=True),
            num_events=int(len(window)),
            num_templates=len(counts),
            num_new_templates=len(new_templates),
            new_template_rate=float(new_template_rate),
            template_frequency_vector=json.dumps(vector, sort_keys=True),
            distribution_divergence=float(divergence),
            drift_magnitude=float(magnitude),
            persistence=self._persistence,
            anomaly_evidence=float(np.mean(anomaly_scores)),
        )
        if self._frozen_reference is None:
            self._history.append(counts)
        self._seen_templates.update(counts)
        return features


def jensen_shannon_divergence(left: Counter[str], right: Counter[str]) -> float:
    """Return base-2 Jensen-Shannon divergence in [0, 1]."""
    keys = sorted(set(left) | set(right))
    if not keys or sum(left.values()) == 0 or sum(right.values()) == 0:
        return 0.0
    p = np.array([left[key] for key in keys], dtype=float)
    q = np.array([right[key] for key in keys], dtype=float)
    p /= p.sum()
    q /= q.sum()
    midpoint = 0.5 * (p + q)
    return float(0.5 * _kl(p, midpoint) + 0.5 * _kl(q, midpoint))


def _kl(left: np.ndarray, right: np.ndarray) -> float:
    mask = left > 0
    return float(np.sum(left[mask] * np.log2(left[mask] / right[mask])))
