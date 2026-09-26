from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from adaptive_lad.config import ScenarioConfig, load_yaml
from adaptive_lad.data.bgl import make_demo_events, prepare_bgl
from adaptive_lad.drift.generator import generate_scenario, stationary_reference_window_ids
from adaptive_lad.evaluation.eda import run_bgl_eda
from adaptive_lad.experiments.batch import run_bgl_batch
from adaptive_lad.experiments.runner import RunResult, run_experiment
from adaptive_lad.io import (
    environment_manifest,
    frame_sha256,
    read_table,
    sha256_file,
    write_json,
    write_table,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DETECTOR = ROOT / "configs/detector/deep_log.yaml"
DEMO_DETECTOR = ROOT / "configs/detector/template_frequency.yaml"
DEFAULT_CHARACTERIZATION = ROOT / "configs/characterization/default.yaml"
DEFAULT_POLICY = ROOT / "configs/policy/default.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adaptive-lad",
        description="Reproducible drift-aware log anomaly detection experiments",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-bgl", help="Prepare raw/structured BGL data")
    prepare.add_argument("--input", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--window-size", type=int, default=10_000)
    prepare.add_argument("--train-fraction", type=float, default=0.2)
    prepare.add_argument("--validation-fraction", type=float, default=0.2)
    prepare.add_argument("--parser", choices=["drain3", "structured", "regex"], default="drain3")
    prepare.add_argument("--drain-similarity-threshold", type=float, default=0.40)
    prepare.add_argument("--drain-depth", type=int, default=4)
    prepare.add_argument("--drain-max-children", type=int, default=100)

    eda = subparsers.add_parser("eda-bgl", help="Generate reproducible temporal BGL EDA")
    eda.add_argument("--events", required=True, type=Path)
    eda.add_argument("--output", required=True, type=Path)
    eda.add_argument("--window-size", type=int, default=10_000)

    run = subparsers.add_parser("run", help="Run one scenario and one comparison method")
    run.add_argument("--events", required=True, type=Path)
    run.add_argument("--scenario", required=True, type=Path)
    run.add_argument("--method", choices=["static", "periodic", "naive", "proposed"], required=True)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--warmup-windows", type=int, default=5)
    run.add_argument("--evaluation-split", choices=["validation", "test"])
    _add_shared_config_arguments(run, detector_default=DEFAULT_DETECTOR)

    demo = subparsers.add_parser("demo", help="Run S1-S6 x four methods on smoke-test data")
    demo.add_argument("--output", type=Path, default=ROOT / "artifacts/demo")
    demo.add_argument("--clean", action="store_true")
    _add_shared_config_arguments(demo, detector_default=DEMO_DETECTOR)

    batch = subparsers.add_parser("batch-bgl", help="Run paired multi-seed BGL experiments")
    batch.add_argument("--events", required=True, type=Path)
    batch.add_argument(
        "--experiment-config", type=Path, default=ROOT / "configs/experiments/main.yaml"
    )
    batch.add_argument("--phase", choices=["validation", "test"], required=True)
    batch.add_argument("--output", required=True, type=Path)
    batch.add_argument("--seeds", help="Comma-separated override")
    batch.add_argument("--magnitudes", help="Comma-separated override")
    batch.add_argument("--methods", help="Comma-separated override")
    batch.add_argument("--scenarios", help="Comma-separated IDs, for example S1,S6")
    batch.add_argument("--save-details", action="store_true")

    subparsers.add_parser("validate-configs", help="Validate all tracked YAML configs")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "prepare-bgl":
        events = prepare_bgl(
            args.input,
            args.output,
            window_size=args.window_size,
            train_fraction=args.train_fraction,
            validation_fraction=args.validation_fraction,
            parser_implementation=args.parser,
            drain_similarity_threshold=args.drain_similarity_threshold,
            drain_depth=args.drain_depth,
            drain_max_children=args.drain_max_children,
        )
        print(f"Prepared {len(events):,} BGL events -> {args.output}")
    elif args.command == "eda-bgl":
        summary = run_bgl_eda(args.events, args.output, selected_window_size=args.window_size)
        print(f"Generated BGL EDA for {summary['total_events']:,} events -> {args.output}")
    elif args.command == "run":
        _run_command(args)
    elif args.command == "demo":
        _demo_command(args)
    elif args.command == "batch-bgl":
        _batch_command(args)
    elif args.command == "validate-configs":
        count = validate_configs(ROOT / "configs")
        print(f"Validated {count} YAML configuration files")


def validate_configs(config_root: Path) -> int:
    paths = sorted(config_root.rglob("*.yaml"))
    for path in paths:
        value = load_yaml(path)
        if "scenarios" in path.parts:
            ScenarioConfig.from_mapping(value)
    return len(paths)


def _run_command(args: argparse.Namespace) -> None:
    events = read_table(args.events)
    scenario_config = ScenarioConfig.from_yaml(args.scenario)
    evaluation_window_ids: list[int] | None = None
    characterization_reference_ids: list[int] | None = None
    warmup_windows = args.warmup_windows
    scenario_events = events
    if args.evaluation_split:
        split_window_ids = sorted(
            int(value)
            for value in events.loc[events["split"] == args.evaluation_split, "window_id"].unique()
        )
        if not split_window_ids:
            raise ValueError(f"No windows found for evaluation split {args.evaluation_split}")
        evaluation_window_ids = split_window_ids
        if scenario_config.evaluation_end_window is not None:
            evaluation_window_ids = [
                value
                for value in evaluation_window_ids
                if value <= scenario_config.evaluation_end_window
            ]
        scenario_events = events[events["window_id"] <= split_window_ids[-1]].copy()
        warmup_windows = sum(
            int(value) < evaluation_window_ids[0] for value in scenario_events["window_id"].unique()
        )
        if scenario_config.base_mode == "stationary_replay":
            characterization_reference_ids = stationary_reference_window_ids(
                scenario_events, scenario_config
            )
    generated = generate_scenario(scenario_events, scenario_config)
    scenario_dir = args.output / "scenario"
    write_table(generated.events, scenario_dir / "stream.parquet")
    write_json(generated.ground_truth, scenario_dir / "ground_truth.json")
    _write_yaml(scenario_config.to_dict(), scenario_dir / "scenario_config.yaml")
    # Ground truth has now been materialized; only the evaluator sees it below.
    result = _execute_run(
        generated.events,
        generated.ground_truth,
        method=args.method,
        warmup_windows=warmup_windows,
        detector_path=args.detector_config,
        characterization_path=args.characterization_config,
        policy_path=args.policy_config,
        evaluation_window_ids=evaluation_window_ids,
        characterization_reference_window_ids=characterization_reference_ids,
    )
    _write_run(result, args.output)
    manifest = _manifest(
        events=events,
        scenario_config=scenario_config,
        methods=[args.method],
        source_path=args.events,
    )
    write_json(manifest, args.output / "experiment_manifest.json")
    print(f"Completed {scenario_config.scenario_id}/{args.method} -> {args.output}")
    print(pd.Series(result.metrics).to_string())


def _demo_command(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    if args.clean and output.exists():
        _assert_safe_demo_target(output)
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    events = make_demo_events()
    write_table(events, output / "demo_events.parquet")
    experiment_config = load_yaml(ROOT / "configs/experiments/demo.yaml")
    methods = [str(value) for value in experiment_config["methods"]]
    rows: list[dict[str, Any]] = []
    scenario_configs: list[ScenarioConfig] = []
    for relative_path in experiment_config["scenarios"]:
        scenario_path = ROOT / str(relative_path)
        scenario_config = ScenarioConfig.from_yaml(scenario_path)
        scenario_configs.append(scenario_config)
        generated = generate_scenario(events, scenario_config)
        scenario_dir = output / "scenarios" / scenario_config.scenario_id
        write_table(generated.events, scenario_dir / "stream.parquet")
        write_json(generated.ground_truth, scenario_dir / "ground_truth.json")
        _write_yaml(scenario_config.to_dict(), scenario_dir / "scenario_config.yaml")
        for method in methods:
            result = _execute_run(
                generated.events,
                generated.ground_truth,
                method=method,
                warmup_windows=int(experiment_config["warmup_windows"]),
                detector_path=args.detector_config,
                characterization_path=args.characterization_config,
                policy_path=args.policy_config,
            )
            run_dir = output / "runs" / scenario_config.scenario_id / method
            _write_run(result, run_dir)
            rows.append(
                {
                    "scenario_id": scenario_config.scenario_id,
                    "method": method,
                    "seed": scenario_config.random_seed,
                    "drift_magnitude": scenario_config.drift_magnitude,
                    "window_size": scenario_config.window_size,
                    **result.metrics,
                }
            )
    results = pd.DataFrame(rows)
    write_table(results, output / "results_raw.parquet")
    results.to_csv(output / "summary.csv", index=False)
    manifest = {
        **environment_manifest(),
        "experiment_id": experiment_config["experiment_id"],
        "input_kind": "synthetic_smoke_test_not_for_reporting",
        "event_frame_sha256": frame_sha256(events),
        "methods": methods,
        "scenarios": [config.to_dict() for config in scenario_configs],
        "resolved_configs": {
            "detector": load_yaml(args.detector_config),
            "characterization": load_yaml(args.characterization_config),
            "policy": load_yaml(args.policy_config),
            "experiment": experiment_config,
        },
    }
    write_json(manifest, output / "experiment_manifest.json")
    print(f"Completed {len(results)} demo runs -> {output}")
    print(
        results[
            ["scenario_id", "method", "f1", "adaptation_delay", "false_adaptation_rate"]
        ].to_string(index=False)
    )


def _batch_command(args: argparse.Namespace) -> None:
    results = run_bgl_batch(
        read_table(args.events),
        load_yaml(args.experiment_config),
        phase=args.phase,
        output_dir=args.output,
        root=ROOT,
        seeds=_comma_values(args.seeds, int),
        magnitudes=_comma_values(args.magnitudes, float),
        methods=_comma_values(args.methods, str),
        scenario_ids=_comma_values(args.scenarios, str),
        save_details=args.save_details,
    )
    print(f"Completed {len(results)} paired BGL runs -> {args.output}")


def _execute_run(
    events: pd.DataFrame,
    ground_truth: dict[str, Any],
    *,
    method: str,
    warmup_windows: int,
    detector_path: Path,
    characterization_path: Path,
    policy_path: Path,
    evaluation_window_ids: list[int] | None = None,
    characterization_reference_window_ids: list[int] | None = None,
) -> RunResult:
    return run_experiment(
        events,
        ground_truth,
        method=method,
        warmup_windows=warmup_windows,
        detector_config=load_yaml(detector_path),
        characterization_config=load_yaml(characterization_path),
        policy_config=load_yaml(policy_path),
        evaluation_window_ids=evaluation_window_ids,
        characterization_reference_window_ids=characterization_reference_window_ids,
    )


def _write_run(result: RunResult, output: Path) -> None:
    write_table(result.predictions, output / "predictions.parquet")
    write_table(result.drift_features, output / "drift_features.parquet")
    write_table(result.adaptation_events, output / "adaptation_events.parquet")
    write_json(result.metrics, output / "metrics.json")


def _manifest(
    *,
    events: pd.DataFrame,
    scenario_config: ScenarioConfig,
    methods: list[str],
    source_path: Path,
) -> dict[str, Any]:
    return {
        **environment_manifest(),
        "source_path": str(source_path.resolve()),
        "source_sha256": sha256_file(source_path),
        "event_frame_sha256": frame_sha256(events),
        "methods": methods,
        "scenario": scenario_config.to_dict(),
    }


def _write_yaml(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False, allow_unicode=True)


def _add_shared_config_arguments(
    parser: argparse.ArgumentParser, *, detector_default: Path
) -> None:
    parser.add_argument("--detector-config", type=Path, default=detector_default)
    parser.add_argument("--characterization-config", type=Path, default=DEFAULT_CHARACTERIZATION)
    parser.add_argument("--policy-config", type=Path, default=DEFAULT_POLICY)


def _assert_safe_demo_target(path: Path) -> None:
    if path == path.anchor or len(path.parts) < 3:
        raise ValueError(f"Refusing to remove unsafe demo target: {path}")


def _comma_values(value: str | None, converter: Any) -> list[Any] | None:
    if value is None:
        return None
    return [converter(item.strip()) for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
