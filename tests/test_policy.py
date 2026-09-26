import pandas as pd

from adaptive_lad.drift.characterization import DriftFeatures
from adaptive_lad.policies.strategies import ProposedDriftAwarePolicy


def _features(window_id: int, *, persistence: int, anomaly_evidence: float) -> DriftFeatures:
    timestamp = pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=window_id)
    return DriftFeatures(
        window_id=window_id,
        start_time=timestamp,
        end_time=timestamp,
        num_events=100,
        num_templates=3,
        num_new_templates=0,
        new_template_rate=0.0,
        template_frequency_vector="{}",
        distribution_divergence=0.3,
        drift_magnitude=0.2,
        persistence=persistence,
        anomaly_evidence=anomaly_evidence,
    )


def _policy() -> ProposedDriftAwarePolicy:
    return ProposedDriftAwarePolicy(
        divergence_threshold=0.1,
        new_template_rate_threshold=0.03,
        magnitude_threshold=0.08,
        minimum_persistence=6,
        maximum_anomaly_evidence=0.1,
        cooldown_windows=10,
        rearm_stable_windows=3,
    )


def test_transient_burst_shorter_than_persistence_does_not_adapt() -> None:
    policy = _policy()

    decisions = [
        policy.decide(_features(window, persistence=window + 1, anomaly_evidence=0.5))
        for window in range(5)
    ]

    assert not any(decision.decision for decision in decisions)


def test_persistent_signal_adapts_once_until_rearmed() -> None:
    policy = _policy()
    decisions = [
        policy.decide(_features(window, persistence=window + 1, anomaly_evidence=0.5))
        for window in range(20)
    ]

    assert [decision.window_id for decision in decisions if decision.decision] == [5]
