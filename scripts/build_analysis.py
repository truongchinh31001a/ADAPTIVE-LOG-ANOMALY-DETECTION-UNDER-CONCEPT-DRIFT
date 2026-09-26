from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "artifacts/bgl/test_primary_fixed"
SENSITIVITY = ROOT / "artifacts/bgl/test_sensitivity_fixed_seed1101"
DIAGNOSTICS = ROOT / "artifacts/bgl/test_diagnostics_seed1101/runs"
FREQUENCY_DIAGNOSTICS = ROOT / "artifacts/bgl/test_diagnostics_frequency_fixed_seed1101/runs"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"

SCENARIO_LABELS = {
    "BGL_TEST_S1": "S1 Sudden frequency",
    "BGL_TEST_S2": "S2 Gradual frequency",
    "BGL_TEST_S3": "S3 Sudden emergence",
    "BGL_TEST_S4": "S4 Gradual emergence",
    "BGL_TEST_S5": "S5 Transient anomaly",
    "BGL_TEST_S6": "S6 No drift",
}
METHODS = ["static", "periodic", "naive", "proposed"]
COLORS = {
    "static": "#6b7280",
    "periodic": "#f59e0b",
    "naive": "#ef4444",
    "proposed": "#2563eb",
}


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    primary = pd.read_csv(PRIMARY / "results_raw.csv")
    summary = pd.read_csv(PRIMARY / "summary.csv")
    sensitivity = pd.read_csv(SENSITIVITY / "results_raw.csv")
    _validate_primary(primary)
    signal_summary = _signal_summary()
    signal_summary.to_csv(TABLES / "drift_signal_summary.csv", index=False)
    _plot_primary_f1(summary)
    _plot_tradeoff(summary)
    _plot_signals()
    _plot_sensitivity(sensitivity)
    print(f"Wrote analysis figures -> {FIGURES}")
    print(f"Wrote drift signal table -> {TABLES / 'drift_signal_summary.csv'}")


def _validate_primary(primary: pd.DataFrame) -> None:
    keys = ["phase", "scenario_id", "seed", "drift_magnitude", "method"]
    if len(primary) != 120 or primary.duplicated(keys).any():
        raise ValueError("Primary result must contain 120 unique paired runs")
    if sorted(primary["seed"].unique().tolist()) != [1101, 1202, 1303, 1404, 1505]:
        raise ValueError("Primary result does not contain the five frozen test seeds")


def _plot_primary_f1(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    scenario_ids = list(SCENARIO_LABELS)
    x = np.arange(len(scenario_ids))
    width = 0.19
    for index, method in enumerate(METHODS):
        selected = summary[summary["method"] == method].set_index("scenario_id").loc[scenario_ids]
        offset = (index - 1.5) * width
        ax.bar(
            x + offset,
            selected["f1_mean"],
            width,
            yerr=selected["f1_std"].fillna(0),
            capsize=3,
            color=COLORS[method],
            label=method.capitalize(),
        )
    ax.set_ylabel("Event-level F1 (mean +/- SD, 5 seeds)")
    ax.set_xticks(x, [f"S{i}" for i in range(1, 7)])
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncols=4, loc="upper center")
    ax.set_title("Primary held-out test: overall anomaly-detection F1")
    fig.tight_layout()
    fig.savefig(FIGURES / "primary_f1.png", dpi=200)
    plt.close(fig)


def _plot_tradeoff(summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    positive = summary[summary["scenario_id"].isin(list(SCENARIO_LABELS)[:4])]
    x = np.arange(4)
    width = 0.25
    for index, method in enumerate(["periodic", "naive", "proposed"]):
        selected = (
            positive[positive["method"] == method]
            .set_index("scenario_id")
            .loc[list(SCENARIO_LABELS)[:4]]
        )
        axes[0].bar(
            x + (index - 1) * width,
            selected["f1_post_adaptation_mean"],
            width,
            yerr=selected["f1_post_adaptation_std"].fillna(0),
            capsize=3,
            color=COLORS[method],
            label=method.capitalize(),
        )
    axes[0].set_xticks(x, ["S1", "S2", "S3", "S4"])
    axes[0].set_ylim(0, 1.08)
    axes[0].set_ylabel("Post-adaptation F1")
    axes[0].set_title("Update efficacy after the first action")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend()

    methods = ["periodic", "naive", "proposed"]
    far = (
        summary[summary["scenario_id"].isin(["BGL_TEST_S5", "BGL_TEST_S6"])]
        .groupby("method")["false_adaptation_rate_mean"]
        .mean()
        .reindex(methods)
    )
    counts = (
        summary[summary["scenario_id"].isin(["BGL_TEST_S5", "BGL_TEST_S6"])]
        .groupby("method")["adaptation_count_mean"]
        .mean()
        .reindex(methods)
    )
    bars = axes[1].bar(methods, far, color=[COLORS[value] for value in methods])
    axes[1].set_ylim(0, 0.24)
    axes[1].set_ylabel("Mean FAR on S5-S6")
    axes[1].set_title("False adaptation on negative controls")
    axes[1].grid(axis="y", alpha=0.25)
    for bar, count in zip(bars, counts, strict=True):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.008,
            f"{count:.1f} updates",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(FIGURES / "adaptation_tradeoff.png", dpi=200)
    plt.close(fig)


def _diagnostic_runs() -> list[Path]:
    frequency = sorted(FREQUENCY_DIAGNOSTICS.glob("BGL_TEST_S*_seed1101_mag*_proposed"))
    remaining = sorted(DIAGNOSTICS.glob("BGL_TEST_S[3-6]_seed1101_mag*_proposed"))
    return frequency + remaining


def _signal_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for run in _diagnostic_runs():
        features = pd.read_parquet(run / "drift_features.parquet")
        actions = pd.read_parquet(run / "adaptation_events.parquet")
        with (run / "ground_truth.json").open(encoding="utf-8") as handle:
            ground_truth = json.load(handle)
        scenario = ground_truth["scenario"]
        start_value = scenario["start_window"]
        start = (
            int(start_value)
            if start_value is not None
            else int(scenario["evaluation_start_window"])
        )
        pre = features[features["window_id"] < start]
        active = features[features["window_id"] >= start]
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "drift_type": scenario["drift_type"],
                "pre_divergence_mean": pre["distribution_divergence"].mean(),
                "post_divergence_max": active["distribution_divergence"].max(),
                "post_new_template_rate_max": active["new_template_rate"].max(),
                "post_drift_magnitude_max": active["drift_magnitude"].max(),
                "post_anomaly_evidence_max": active["anomaly_evidence"].max(),
                "maximum_persistence": int(features["persistence"].max()),
                "adaptation_windows": ",".join(
                    str(int(value)) for value in actions.loc[actions["decision"], "window_id"]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("scenario_id")


def _plot_signals() -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), sharex=True, sharey=True)
    for ax, run in zip(axes.flat, _diagnostic_runs(), strict=True):
        features = pd.read_parquet(run / "drift_features.parquet")
        actions = pd.read_parquet(run / "adaptation_events.parquet")
        with (run / "ground_truth.json").open(encoding="utf-8") as handle:
            ground_truth = json.load(handle)
        scenario = ground_truth["scenario"]
        ax.plot(features["window_id"], features["drift_magnitude"], label="Drift magnitude")
        ax.plot(
            features["window_id"],
            features["anomaly_evidence"],
            label="Anomaly evidence",
            alpha=0.75,
        )
        if scenario["start_window"] is not None:
            ax.axvline(int(scenario["start_window"]), color="black", linestyle="--", alpha=0.65)
        for window_id in actions.loc[actions["decision"], "window_id"]:
            ax.axvline(int(window_id), color=COLORS["proposed"], linestyle=":", linewidth=2)
        ax.set_title(SCENARIO_LABELS[scenario["scenario_id"]])
        ax.grid(alpha=0.2)
    axes[-1, 0].set_xlabel("Window ID")
    axes[-1, 1].set_xlabel("Window ID")
    for ax in axes[:, 0]:
        ax.set_ylabel("Normalized signal")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncols=2, bbox_to_anchor=(0.5, 0.965))
    fig.suptitle("Drift and anomaly evidence (seed 1101; dashed=onset, dotted=adaptation)", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(FIGURES / "drift_signals.png", dpi=200)
    plt.close(fig)


def _plot_sensitivity(sensitivity: pd.DataFrame) -> None:
    proposed = sensitivity[
        (sensitivity["method"] == "proposed")
        & sensitivity["scenario_id"].isin(list(SCENARIO_LABELS)[:4])
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    for scenario_id, group in proposed.groupby("scenario_id"):
        ordered = group.sort_values("drift_magnitude")
        label = scenario_id.rsplit("_", 1)[-1]
        axes[0].plot(ordered["drift_magnitude"], ordered["f1"], marker="o", label=label)
        axes[1].plot(
            ordered["drift_magnitude"], ordered["adaptation_delay"], marker="o", label=label
        )
    axes[0].set_ylabel("Overall F1")
    axes[1].set_ylabel("Adaptation Delay (windows)")
    for ax in axes:
        ax.set_xlabel("Injected drift magnitude")
        ax.set_xticks([0.10, 0.40])
        ax.grid(alpha=0.25)
        ax.legend()
    axes[0].set_title("Sensitivity of detection quality")
    axes[1].set_title("Sensitivity of response time")
    fig.tight_layout()
    fig.savefig(FIGURES / "sensitivity.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
