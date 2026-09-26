from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from adaptive_lad.drift.characterization import DriftFeatures


@dataclass(frozen=True)
class AdaptationDecision:
    window_id: int
    decision: bool
    decision_score: float
    reason: str
    action: str
    method: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AdaptationPolicy(Protocol):
    def decide(self, features: DriftFeatures) -> AdaptationDecision: ...


class StaticPolicy:
    name = "static"

    def decide(self, features: DriftFeatures) -> AdaptationDecision:
        return _decision(features, False, 0.0, "static detector", self.name)


class PeriodicPolicy:
    name = "periodic"

    def __init__(self, interval: int, first_evaluation_window: int) -> None:
        self.interval = interval
        self.first_evaluation_window = first_evaluation_window

    def decide(self, features: DriftFeatures) -> AdaptationDecision:
        elapsed = features.window_id - self.first_evaluation_window + 1
        adapt = elapsed > 0 and elapsed % self.interval == 0
        return _decision(
            features,
            adapt,
            float(adapt),
            f"fixed interval={self.interval}",
            self.name,
        )


class NaivePolicy:
    name = "naive"

    def __init__(self, divergence_threshold: float, cooldown_windows: int) -> None:
        self.divergence_threshold = divergence_threshold
        self.cooldown_windows = cooldown_windows
        self.last_adaptation: int | None = None

    def decide(self, features: DriftFeatures) -> AdaptationDecision:
        alarm = features.distribution_divergence >= self.divergence_threshold
        cooldown = (
            self.last_adaptation is not None
            and features.window_id - self.last_adaptation <= self.cooldown_windows
        )
        adapt = alarm and not cooldown
        if adapt:
            self.last_adaptation = features.window_id
        reason = "raw divergence alarm" if alarm else "below divergence threshold"
        if cooldown:
            reason = "cooldown"
        return _decision(features, adapt, features.distribution_divergence, reason, self.name)


class ProposedDriftAwarePolicy:
    name = "proposed"

    def __init__(
        self,
        *,
        divergence_threshold: float,
        new_template_rate_threshold: float,
        magnitude_threshold: float,
        minimum_persistence: int,
        maximum_anomaly_evidence: float,
        cooldown_windows: int,
        rearm_stable_windows: int,
    ) -> None:
        self.divergence_threshold = divergence_threshold
        self.new_template_rate_threshold = new_template_rate_threshold
        self.magnitude_threshold = magnitude_threshold
        self.minimum_persistence = minimum_persistence
        self.maximum_anomaly_evidence = maximum_anomaly_evidence
        self.cooldown_windows = cooldown_windows
        self.rearm_stable_windows = rearm_stable_windows
        self.last_adaptation: int | None = None
        self.last_emergence_signal: int | None = None
        self.stable_windows = 0
        self.armed = True

    def decide(self, features: DriftFeatures) -> AdaptationDecision:
        structural_signal = (
            features.distribution_divergence >= self.divergence_threshold
            or features.new_template_rate >= self.new_template_rate_threshold
        )
        if features.new_template_rate >= self.new_template_rate_threshold:
            self.last_emergence_signal = features.window_id
        recent_emergence = (
            self.last_emergence_signal is not None
            and features.window_id - self.last_emergence_signal <= self.minimum_persistence
        )
        persistent = features.persistence >= self.minimum_persistence
        large_enough = features.drift_magnitude >= self.magnitude_threshold
        # High anomaly evidence without template emergence is treated as a burst, not a
        # new normal regime. Emergence may itself cause high detector scores.
        transient_guard = (
            features.anomaly_evidence > self.maximum_anomaly_evidence
            and not recent_emergence
            and features.persistence < self.minimum_persistence
        )
        active_regime_signal = structural_signal and large_enough
        if active_regime_signal:
            self.stable_windows = 0
        else:
            self.stable_windows += 1
            if self.stable_windows >= self.rearm_stable_windows:
                self.armed = True
        cooldown = (
            self.last_adaptation is not None
            and features.window_id - self.last_adaptation <= self.cooldown_windows
        )
        adapt = (
            structural_signal
            and persistent
            and large_enough
            and not transient_guard
            and not cooldown
            and self.armed
        )
        if adapt:
            self.last_adaptation = features.window_id
            self.armed = False
        checks = {
            "structural": structural_signal,
            "persistent": persistent,
            "magnitude": large_enough,
            "recent_emergence": recent_emergence,
            "transient_guard": transient_guard,
            "cooldown": cooldown,
            "armed": self.armed,
        }
        reason = ", ".join(f"{name}={value}" for name, value in checks.items())
        return _decision(features, adapt, features.drift_magnitude, reason, self.name)


def build_policy(
    method: str, config: dict[str, Any], *, first_evaluation_window: int
) -> AdaptationPolicy:
    if method == "static":
        return StaticPolicy()
    if method == "periodic":
        return PeriodicPolicy(int(config["periodic_interval"]), first_evaluation_window)
    if method == "naive":
        return NaivePolicy(float(config["divergence_threshold"]), int(config["cooldown_windows"]))
    if method == "proposed":
        return ProposedDriftAwarePolicy(
            divergence_threshold=float(config["divergence_threshold"]),
            new_template_rate_threshold=float(config["new_template_rate_threshold"]),
            magnitude_threshold=float(config["magnitude_threshold"]),
            minimum_persistence=int(config["minimum_persistence"]),
            maximum_anomaly_evidence=float(config["maximum_anomaly_evidence"]),
            cooldown_windows=int(config["cooldown_windows"]),
            rearm_stable_windows=int(config.get("rearm_stable_windows", 3)),
        )
    raise ValueError(f"Unknown method: {method}")


def _decision(
    features: DriftFeatures, adapt: bool, score: float, reason: str, method: str
) -> AdaptationDecision:
    return AdaptationDecision(
        window_id=features.window_id,
        decision=adapt,
        decision_score=float(score),
        reason=reason,
        action="update" if adapt else "none",
        method=method,
    )
