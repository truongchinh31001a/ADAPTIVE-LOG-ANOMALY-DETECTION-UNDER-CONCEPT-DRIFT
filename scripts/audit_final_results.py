from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/bgl"
RUN_KEYS = ["phase", "scenario_id", "seed", "drift_magnitude", "method"]
METRICS = [
    "f1",
    "f1_post_adaptation",
    "adaptation_delay",
    "false_adaptation_rate",
    "adaptation_count",
]
SEEDS = [1101, 1202, 1303, 1404, 1505]
METHODS = ["static", "periodic", "naive", "proposed"]


def main() -> None:
    primary = pd.read_csv(ARTIFACTS / "test_primary_fixed/results_raw.csv")
    _assert_unique(primary, expected_rows=120)
    assert sorted(primary["seed"].unique().tolist()) == SEEDS
    assert sorted(primary["method"].unique().tolist()) == sorted(METHODS)
    assert sorted(primary["scenario_id"].unique().tolist()) == [
        f"BGL_TEST_S{index}" for index in range(1, 7)
    ]

    proposed = primary[primary["method"] == "proposed"]
    persistent = proposed[proposed["scenario_id"].isin([f"BGL_TEST_S{i}" for i in range(1, 5)])]
    controls = proposed[proposed["scenario_id"].isin(["BGL_TEST_S5", "BGL_TEST_S6"])]
    assert len(persistent) == 20 and (persistent["adaptation_count"] == 1).all()
    assert (persistent["false_adaptation_rate"] == 0).all()
    assert len(controls) == 10 and (controls["adaptation_count"] == 0).all()
    assert (controls["false_adaptation_rate"] == 0).all()

    fixed_frequency = pd.concat(
        [
            pd.read_csv(ARTIFACTS / f"test_frequency_fixed_seed{seed}/results_raw.csv")
            for seed in SEEDS
        ],
        ignore_index=True,
    )
    _assert_matches(primary, fixed_frequency)
    stable_original = pd.read_csv(ARTIFACTS / "test_primary/results_raw.csv")
    stable_scenarios = [f"BGL_TEST_S{i}" for i in range(3, 7)]
    stable_original = stable_original[stable_original["scenario_id"].isin(stable_scenarios)]
    _assert_matches(primary, stable_original)

    sensitivity = pd.read_csv(ARTIFACTS / "test_sensitivity_fixed_seed1101/results_raw.csv")
    _assert_unique(sensitivity, expected_rows=44)
    sensitivity_proposed = sensitivity[sensitivity["method"] == "proposed"]
    assert (sensitivity_proposed["false_adaptation_rate"] == 0).all()
    assert (
        sensitivity_proposed[
            sensitivity_proposed["scenario_id"].isin(["BGL_TEST_S5", "BGL_TEST_S6"])
        ]["adaptation_count"]
        == 0
    ).all()

    for scenario in ["S1", "S2"]:
        primary_truth = _read_json(
            ARTIFACTS
            / "test_frequency_fixed_seed1101/runs"
            / f"BGL_TEST_{scenario}_seed1101_mag0.25_proposed/ground_truth.json"
        )
        diagnostic_truth = _read_json(
            ARTIFACTS
            / "test_diagnostics_frequency_fixed_seed1101/runs"
            / f"BGL_TEST_{scenario}_seed1101_mag0.25_proposed/ground_truth.json"
        )
        assert primary_truth["stream_sha256"] == diagnostic_truth["stream_sha256"]

    merge_manifest = _read_json(ARTIFACTS / "test_primary_fixed/merge_manifest.json")
    assert merge_manifest["run_count"] == 120
    assert merge_manifest["replace_duplicates"] is True
    print("Final audit passed: 120 primary runs, 44 sensitivity runs, fixed hashes/invariants OK")


def _assert_unique(frame: pd.DataFrame, *, expected_rows: int) -> None:
    assert len(frame) == expected_rows
    assert not frame.duplicated(RUN_KEYS).any()


def _assert_matches(final: pd.DataFrame, source: pd.DataFrame) -> None:
    merged = source.merge(final, on=RUN_KEYS, suffixes=("_source", "_final"), validate="one_to_one")
    assert len(merged) == len(source)
    for metric in METRICS:
        left = merged[f"{metric}_source"].fillna(-1.0)
        right = merged[f"{metric}_final"].fillna(-1.0)
        assert left.equals(right), metric


def _read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    main()
