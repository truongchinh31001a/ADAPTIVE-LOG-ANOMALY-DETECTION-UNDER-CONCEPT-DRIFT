from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from adaptive_lad.config import ScenarioConfig
from adaptive_lad.io import frame_sha256


@dataclass(frozen=True)
class GeneratedScenario:
    events: pd.DataFrame
    ground_truth: dict[str, Any]


def generate_scenario(events: pd.DataFrame, config: ScenarioConfig) -> GeneratedScenario:
    """Generate a scenario without consulting any detector or adaptation policy."""
    _validate_events(events)
    rng = np.random.default_rng(config.random_seed)
    heldout_mask = (
        events["heldout_only"].astype(bool)
        if "heldout_only" in events.columns
        else pd.Series(False, index=events.index)
    )
    heldout = events.loc[heldout_mask].copy()
    stream = events.loc[~heldout_mask].copy().reset_index(drop=True)
    _validate_window_size(stream, config.window_size)
    emergence_pool = pd.concat([heldout, stream], ignore_index=True)
    replay_already_applied = "_stationary_replay_applied" in stream and bool(
        stream["_stationary_replay_applied"].all()
    )
    if config.base_mode == "stationary_replay" and not replay_already_applied:
        stream = _stationary_replay(stream, config, rng)

    if config.drift_type == "frequency":
        stream = _inject_frequency_drift(stream, config, rng)
    elif config.drift_type == "emergence":
        stream = _inject_emergence(stream, emergence_pool, config, rng)
    elif config.drift_type == "transient_anomaly":
        stream = _inject_transient_anomalies(stream, config, rng)
    elif config.drift_type != "none":
        raise ValueError(f"Unsupported drift type: {config.drift_type}")

    stream = stream.sort_values(["window_id", "timestamp", "event_uid"], kind="stable")
    stream = stream.reset_index(drop=True)
    stream["scenario_id"] = config.scenario_id
    stream["drift_label"] = [
        _drift_label_for_window(int(window_id), config) for window_id in stream["window_id"]
    ]
    ground_truth = _ground_truth(config, stream)
    return GeneratedScenario(events=stream, ground_truth=ground_truth)


def _inject_frequency_drift(
    stream: pd.DataFrame, config: ScenarioConfig, rng: np.random.Generator
) -> pd.DataFrame:
    assert config.start_window is not None
    if config.base_mode == "stationary_replay":
        reference_ids = stationary_reference_window_ids(stream, config)
        pre_drift = stream[stream["window_id"].isin(reference_ids) & (stream["anomaly_label"] == 0)]
    else:
        pre_drift = stream[
            (stream["window_id"] < config.start_window) & (stream["anomaly_label"] == 0)
        ]
    frequencies = pre_drift["template_id"].value_counts(normalize=True)
    if len(frequencies) < 2:
        raise ValueError("Frequency drift requires at least two normal templates before drift")
    templates = list(config.affected_templates) or frequencies.index.tolist()
    templates = [template for template in templates if template in frequencies.index]
    if len(templates) < 2:
        raise ValueError("At least two affected templates must exist before frequency drift")

    base = frequencies.reindex(templates, fill_value=0.0).to_numpy(dtype=float)
    base /= base.sum()
    target = (1 - config.drift_magnitude) * base + config.drift_magnitude * base[::-1]
    target /= target.sum()
    pool = {template: pre_drift[pre_drift["template_id"] == template] for template in templates}
    result = stream.copy()
    for window_id in sorted(result["window_id"].unique()):
        if config.evaluation_end_window is not None and window_id > config.evaluation_end_window:
            continue
        progress = _drift_progress(int(window_id), config)
        if progress <= 0:
            continue
        probabilities = (1 - progress) * base + progress * target
        candidate_index = result.index[
            (result["window_id"] == window_id)
            & (result["anomaly_label"] == 0)
            & result["template_id"].isin(templates)
        ].to_numpy()
        if not len(candidate_index):
            continue
        sampled_templates = rng.choice(templates, size=len(candidate_index), p=probabilities)
        # Stable ordering is required because each template consumes RNG draws below.
        # Iterating a set made the generated stream depend on PYTHONHASHSEED.
        for template_id in sorted(set(sampled_templates)):
            targets = candidate_index[sampled_templates == template_id]
            template_pool = pool[str(template_id)]
            sources = template_pool.iloc[rng.integers(len(template_pool), size=len(targets))]
            _copy_log_identities(result, targets, sources, anomaly_label=0)
    return result


def _stationary_replay(
    stream: pd.DataFrame,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Replace evaluation windows with clean pre-evaluation windows plus stable anomalies."""
    assert config.evaluation_start_window is not None
    reference = stream[stream["window_id"] < config.evaluation_start_window]
    clean_ids = stationary_reference_window_ids(stream, config)
    if not clean_ids:
        raise ValueError("stationary_replay requires an anomaly-free reference window")
    clean_windows = [reference[reference["window_id"] == window_id] for window_id in clean_ids]
    anomaly_pool = reference[reference["anomaly_label"] == 1]
    if config.background_anomaly_rate > 0 and anomaly_pool.empty:
        raise ValueError("stationary_replay requested anomalies but the reference has none")

    result = stream.copy()
    identity_columns = [
        column
        for column in [
            "host",
            "component",
            "raw_message",
            "parsed_message",
            "template_id",
            "parameters",
        ]
        if column in result
    ]
    evaluation_ids = sorted(
        int(value)
        for value in result.loc[
            result["window_id"] >= config.evaluation_start_window, "window_id"
        ].unique()
    )
    for window_id in evaluation_ids:
        if config.evaluation_end_window is not None and window_id > config.evaluation_end_window:
            continue
        target_index = result.index[result["window_id"] == window_id].to_numpy()
        source_window = clean_windows[int(rng.integers(len(clean_windows)))]
        repetitions = int(np.ceil(len(target_index) / len(source_window)))
        source = pd.concat([source_window] * repetitions, ignore_index=True).iloc[
            : len(target_index)
        ]
        result.loc[target_index, identity_columns] = source[identity_columns].to_numpy()
        result.loc[target_index, "anomaly_label"] = 0
        result.loc[target_index, "source_event_uid"] = source["event_uid"].to_numpy()

        anomaly_count = int(round(len(target_index) * config.background_anomaly_rate))
        if anomaly_count:
            anomaly_targets = rng.choice(target_index, size=anomaly_count, replace=False)
            anomaly_sources = anomaly_pool.iloc[rng.integers(len(anomaly_pool), size=anomaly_count)]
            result.loc[anomaly_targets, identity_columns] = anomaly_sources[
                identity_columns
            ].to_numpy()
            result.loc[anomaly_targets, "anomaly_label"] = 1
            result.loc[anomaly_targets, "source_event_uid"] = anomaly_sources[
                "event_uid"
            ].to_numpy()
    result["_stationary_replay_applied"] = True
    return result


def stationary_reference_window_ids(stream: pd.DataFrame, config: ScenarioConfig) -> list[int]:
    """Return the latest clean, sufficiently diverse pre-evaluation reference windows."""
    if config.evaluation_start_window is None:
        raise ValueError("Reference selection requires evaluation_start_window")
    reference = stream[stream["window_id"] < config.evaluation_start_window]
    candidates: list[int] = []
    for window_id, window in reference.groupby("window_id", sort=True):
        if int(window["anomaly_label"].sum()) != 0:
            continue
        frequencies = window["template_id"].value_counts(normalize=True)
        dominant = int((frequencies >= config.reference_min_template_fraction).sum())
        if (
            len(frequencies) >= config.reference_min_templates
            and dominant >= config.reference_min_dominant_templates
        ):
            candidates.append(int(window_id))
    selected = candidates[-config.reference_window_count :]
    if not selected:
        raise ValueError("No clean window satisfies the stationary reference rule")
    return selected


def _inject_emergence(
    stream: pd.DataFrame,
    heldout: pd.DataFrame,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    templates = list(config.affected_templates)
    if not templates:
        raise ValueError("Emergence scenarios require affected_templates")
    pool = heldout[heldout["template_id"].isin(templates)].copy()
    if pool.empty:
        # On a real dataset, selected future templates are hidden without changing
        # the stream length: their natural rows are replaced by pre-drift normals.
        pool = stream[stream["template_id"].isin(templates)].copy()
        assert config.start_window is not None
        replacement_pool = stream[
            (stream["window_id"] < config.start_window)
            & (stream["anomaly_label"] == 0)
            & ~stream["template_id"].isin(templates)
        ]
        if replacement_pool.empty:
            raise ValueError("No pre-drift normal rows can replace held-out templates")
        stream = stream.copy()
        heldout_indices = stream.index[stream["template_id"].isin(templates)]
        replacement_sources = replacement_pool.iloc[
            rng.integers(len(replacement_pool), size=len(heldout_indices))
        ]
        _copy_log_identities(
            stream, heldout_indices.to_numpy(), replacement_sources, anomaly_label=0
        )
    if pool.empty:
        raise ValueError("No held-out normal rows found for the configured emergence templates")
    if (pool["anomaly_label"] != 0).any():
        raise ValueError("Emergence templates must come from normal held-out events")

    result = stream.copy().reset_index(drop=True)
    for window_id in sorted(result["window_id"].unique()):
        if config.evaluation_end_window is not None and window_id > config.evaluation_end_window:
            continue
        progress = _drift_progress(int(window_id), config)
        if progress <= 0:
            continue
        normal_index = result.index[
            (result["window_id"] == window_id) & (result["anomaly_label"] == 0)
        ].to_numpy()
        replacement_count = min(
            len(normal_index), int(round(len(normal_index) * config.drift_magnitude * progress))
        )
        if replacement_count == 0:
            continue
        replace_index = rng.choice(normal_index, size=replacement_count, replace=False)
        sources = pool.iloc[rng.integers(len(pool), size=replacement_count)]
        _copy_log_identities(result, replace_index, sources, anomaly_label=0)
    return result


def _inject_transient_anomalies(
    stream: pd.DataFrame, config: ScenarioConfig, rng: np.random.Generator
) -> pd.DataFrame:
    assert config.start_window is not None and config.end_window is not None
    anomaly_pool = stream[stream["anomaly_label"] == 1]
    if anomaly_pool.empty:
        raise ValueError("Transient-anomaly generation requires anomaly examples")
    result = stream.copy()
    for window_id in range(config.start_window, config.end_window + 1):
        normal_index = result.index[
            (result["window_id"] == window_id) & (result["anomaly_label"] == 0)
        ].to_numpy()
        replacement_count = min(
            len(normal_index), int(round(len(normal_index) * config.drift_magnitude))
        )
        if replacement_count == 0:
            continue
        replace_index = rng.choice(normal_index, size=replacement_count, replace=False)
        sources = anomaly_pool.iloc[rng.integers(len(anomaly_pool), size=replacement_count)]
        _copy_log_identities(result, replace_index, sources, anomaly_label=1)
    return result


def _copy_log_identities(
    frame: pd.DataFrame,
    target_indices: np.ndarray,
    sources: pd.DataFrame,
    *,
    anomaly_label: int,
) -> None:
    columns = [
        column
        for column in [
            "host",
            "component",
            "raw_message",
            "parsed_message",
            "template_id",
            "parameters",
        ]
        if column in frame and column in sources
    ]
    frame.loc[target_indices, columns] = sources[columns].to_numpy()
    frame.loc[target_indices, "anomaly_label"] = anomaly_label
    frame.loc[target_indices, "source_event_uid"] = sources["event_uid"].to_numpy()


def _drift_progress(window_id: int, config: ScenarioConfig) -> float:
    if (
        config.drift_type == "none"
        or config.start_window is None
        or window_id < config.start_window
    ):
        return 0.0
    if config.temporal_pattern == "sudden":
        return 1.0
    assert config.end_window is not None
    if config.end_window == config.start_window:
        return 1.0
    return min(
        1.0, (window_id - config.start_window + 1) / (config.end_window - config.start_window + 1)
    )


def _drift_label_for_window(window_id: int, config: ScenarioConfig) -> str:
    if config.drift_type == "none" or config.start_window is None:
        return "none"
    if config.drift_type == "transient_anomaly":
        assert config.end_window is not None
        return (
            "transient_anomaly" if config.start_window <= window_id <= config.end_window else "none"
        )
    return config.drift_type if window_id >= config.start_window else "none"


def _ground_truth(config: ScenarioConfig, stream: pd.DataFrame) -> dict[str, Any]:
    requires_adaptation = config.drift_type in {"frequency", "emergence"}
    episodes: list[dict[str, int | str]] = []
    if requires_adaptation:
        assert config.start_window is not None and config.end_window is not None
        episodes.append(
            {
                "drift_type": config.drift_type,
                "drift_start": config.start_window,
                "drift_end": config.end_window,
                "valid_adaptation_start": config.start_window,
                "valid_adaptation_end": config.end_window + config.tolerance_horizon,
            }
        )
    invalid_regions: list[dict[str, int | str]] = []
    if config.drift_type == "transient_anomaly":
        assert config.start_window is not None and config.end_window is not None
        invalid_regions.append(
            {
                "reason": "transient_anomaly",
                "start_window": config.start_window,
                "end_window": config.end_window,
            }
        )
    if config.drift_type == "none":
        invalid_regions.append(
            {
                "reason": "no_drift",
                "start_window": int(stream["window_id"].min()),
                "end_window": int(stream["window_id"].max()),
            }
        )
    return {
        "scenario": config.to_dict(),
        "requires_adaptation": requires_adaptation,
        "episodes": episodes,
        "invalid_regions": invalid_regions,
        "stream_sha256": frame_sha256(stream),
    }


def _validate_events(events: pd.DataFrame) -> None:
    required = {"event_uid", "timestamp", "template_id", "anomaly_label", "window_id"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Event table is missing columns: {sorted(missing)}")
    if events["event_uid"].duplicated().any():
        raise ValueError("event_uid must be unique")


def _validate_window_size(events: pd.DataFrame, expected: int) -> None:
    counts = events.groupby("window_id").size()
    if counts.empty:
        raise ValueError("Scenario input has no temporal windows")
    final_window = counts.index.max()
    invalid = counts[(counts.index != final_window) & (counts != expected)]
    if not invalid.empty or counts.loc[final_window] > expected:
        observed = sorted(int(value) for value in counts.unique())
        raise ValueError(
            f"Scenario window_size={expected} does not match observed window sizes {observed}"
        )
