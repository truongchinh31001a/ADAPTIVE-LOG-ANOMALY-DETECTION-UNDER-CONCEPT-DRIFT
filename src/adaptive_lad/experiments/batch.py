from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_lad.config import ScenarioConfig, load_yaml
from adaptive_lad.detectors.factory import build_detector
from adaptive_lad.drift.generator import generate_scenario, stationary_reference_window_ids
from adaptive_lad.experiments.runner import run_experiment
from adaptive_lad.io import environment_manifest, frame_sha256, write_json, write_table


def run_bgl_batch(
    events: pd.DataFrame,
    experiment_config: dict[str, Any],
    *,
    phase: str,
    output_dir: str | Path,
    root: str | Path,
    seeds: list[int] | None = None,
    magnitudes: list[float] | None = None,
    methods: list[str] | None = None,
    scenario_ids: list[str] | None = None,
    save_details: bool = False,
) -> pd.DataFrame:
    if phase not in {"validation", "test"}:
        raise ValueError("phase must be validation or test")
    project_root = Path(root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    seeds = seeds or [int(value) for value in experiment_config[f"{phase}_seeds"]]
    magnitudes = magnitudes or [float(value) for value in experiment_config["drift_magnitudes"]]
    methods = methods or [str(value) for value in experiment_config["methods"]]
    scenario_root = project_root / str(experiment_config[f"{phase}_scenarios"])
    scenario_configs = [
        ScenarioConfig.from_yaml(path) for path in sorted(scenario_root.glob("*.yaml"))
    ]
    if len(scenario_configs) != 6:
        raise ValueError(f"Expected six scenarios under {scenario_root}")
    selected_scenarios = scenario_configs
    if scenario_ids:
        wanted = {value.upper() for value in scenario_ids}
        selected_scenarios = [
            config
            for config in scenario_configs
            if config.scenario_id.upper() in wanted
            or config.scenario_id.rsplit("_", 1)[-1].upper() in wanted
        ]
        if not selected_scenarios:
            raise ValueError(f"No scenarios matched {sorted(wanted)}")
    evaluation_start = int(experiment_config[f"{phase}_warmup_windows"])
    split_name = str(experiment_config[f"{phase}_split"])
    evaluation_end_values = {config.evaluation_end_window for config in scenario_configs}
    if len(evaluation_end_values) != 1 or None in evaluation_end_values:
        raise ValueError("Batch scenarios must share one explicit evaluation_end_window")
    evaluation_end_value = next(iter(evaluation_end_values))
    assert evaluation_end_value is not None
    evaluation_end = int(evaluation_end_value)
    evaluation_ids = sorted(
        int(value)
        for value in events.loc[
            (events["split"] == split_name)
            & events["window_id"].between(evaluation_start, evaluation_end),
            "window_id",
        ].unique()
    )
    phase_end = int(events.loc[events["split"] == split_name, "window_id"].max())
    phase_events = events[events["window_id"] <= phase_end].copy()
    training = phase_events[phase_events["window_id"] < evaluation_start]
    characterization_reference_ids = stationary_reference_window_ids(
        phase_events, scenario_configs[0]
    )
    detector_config_base = load_yaml(project_root / str(experiment_config["detector_config"]))
    characterization_config = load_yaml(
        project_root / str(experiment_config["characterization_config"])
    )
    policy_config = load_yaml(project_root / str(experiment_config["policy_config"]))

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        detector_config = {**detector_config_base, "random_seed": seed}
        initial_detector = build_detector(detector_config)
        initial_detector.fit(training)
        no_drift = next(config for config in scenario_configs if config.drift_type == "none")
        stationary_config = replace(no_drift, random_seed=seed)
        stationary = generate_scenario(phase_events, stationary_config).events
        emergence_templates = {
            template
            for config in scenario_configs
            if config.drift_type == "emergence"
            for template in config.affected_templates
        }
        heldout_pool = phase_events[phase_events["template_id"].isin(emergence_templates)].copy()
        heldout_pool["event_uid"] = "pool-" + heldout_pool["event_uid"].astype(str)
        heldout_pool["heldout_only"] = True
        stationary["heldout_only"] = False
        stationary_with_pool = pd.concat([stationary, heldout_pool], ignore_index=True)
        for scenario in selected_scenarios:
            scenario_magnitudes = [0.0] if scenario.drift_type == "none" else magnitudes
            for magnitude in scenario_magnitudes:
                resolved = replace(
                    scenario,
                    random_seed=seed,
                    drift_magnitude=magnitude,
                )
                generated = generate_scenario(stationary_with_pool, resolved)
                for method in methods:
                    print(
                        f"[{phase}] {resolved.scenario_id} seed={seed} "
                        f"magnitude={magnitude:.2f} method={method}",
                        flush=True,
                    )
                    result = run_experiment(
                        generated.events,
                        generated.ground_truth,
                        method=method,
                        warmup_windows=evaluation_start,
                        detector_config=detector_config,
                        characterization_config=characterization_config,
                        policy_config=policy_config,
                        evaluation_window_ids=evaluation_ids,
                        prefitted_detector=copy.deepcopy(initial_detector),
                        characterization_reference_window_ids=characterization_reference_ids,
                    )
                    run_id = f"{resolved.scenario_id}_seed{seed}_mag{magnitude:.2f}_{method}"
                    run_dir = output / "runs" / run_id
                    write_json(result.metrics, run_dir / "metrics.json")
                    write_json(generated.ground_truth, run_dir / "ground_truth.json")
                    write_json(resolved.to_dict(), run_dir / "scenario_config.json")
                    if save_details:
                        write_table(result.predictions, run_dir / "predictions.parquet")
                        write_table(result.drift_features, run_dir / "drift_features.parquet")
                        write_table(result.adaptation_events, run_dir / "adaptation_events.parquet")
                    rows.append(
                        {
                            "phase": phase,
                            "scenario_id": resolved.scenario_id,
                            "drift_type": resolved.drift_type,
                            "temporal_pattern": resolved.temporal_pattern,
                            "seed": seed,
                            "drift_magnitude": magnitude,
                            "method": method,
                            **result.metrics,
                        }
                    )
    results = pd.DataFrame(rows)
    write_table(results, output / "results_raw.parquet")
    results.to_csv(output / "results_raw.csv", index=False)
    summary = summarize_results(results)
    summary.to_csv(output / "summary.csv", index=False)
    write_json(
        {
            **environment_manifest(),
            "experiment_id": experiment_config["experiment_id"],
            "phase": phase,
            "seeds": seeds,
            "magnitudes": magnitudes,
            "methods": methods,
            "selected_scenarios": [config.scenario_id for config in selected_scenarios],
            "evaluation_window_ids": evaluation_ids,
            "characterization_reference_window_ids": characterization_reference_ids,
            "input_frame_sha256": frame_sha256(phase_events),
            "detector_config": detector_config_base,
            "characterization_config": characterization_config,
            "policy_config": policy_config,
            "scenario_configs": [config.to_dict() for config in scenario_configs],
        },
        output / "experiment_manifest.json",
    )
    return results


def summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "f1",
        "f1_post_adaptation",
        "adaptation_delay",
        "false_adaptation_rate",
        "adaptation_count",
    ]
    summary = (
        results.groupby(
            ["phase", "scenario_id", "drift_type", "temporal_pattern", "drift_magnitude", "method"],
            dropna=False,
        )[metrics]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.columns = [
        "_".join(str(part) for part in column if part).rstrip("_")
        if isinstance(column, tuple)
        else str(column)
        for column in summary.columns
    ]
    return summary
