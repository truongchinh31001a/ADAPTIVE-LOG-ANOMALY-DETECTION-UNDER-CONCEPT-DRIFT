from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_lad.drift.characterization import jensen_shannon_divergence
from adaptive_lad.io import read_table, write_json


def summarize_windows(events: pd.DataFrame, window_size: int) -> pd.DataFrame:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    required = {"timestamp", "template_id", "anomaly_label"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"EDA input is missing columns: {sorted(missing)}")
    frame = events.loc[:, sorted(required)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    frame["window_id"] = np.arange(len(frame), dtype=np.int64) // window_size
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous: Counter[str] | None = None
    for window_id, window in frame.groupby("window_id", sort=True):
        counts = Counter(window["template_id"].astype(str))
        new_templates = set(counts) - seen
        rows.append(
            {
                "window_id": int(window_id),
                "start_time": window["timestamp"].min(),
                "end_time": window["timestamp"].max(),
                "num_events": int(len(window)),
                "duration_hours": float(
                    (window["timestamp"].max() - window["timestamp"].min()).total_seconds() / 3600
                ),
                "num_templates": len(counts),
                "num_new_templates": len(new_templates),
                "new_template_rate": float(
                    sum(counts[template] for template in new_templates) / len(window)
                ),
                "anomaly_ratio": float(window["anomaly_label"].mean()),
                "distribution_divergence": (
                    float(jensen_shannon_divergence(previous, counts))
                    if previous is not None
                    else np.nan
                ),
            }
        )
        seen.update(counts)
        previous = counts
    return pd.DataFrame(rows)


def compare_window_sizes(
    events: pd.DataFrame,
    sizes: tuple[int, ...] = (5_000, 10_000, 20_000),
    *,
    development_fraction: float = 0.40,
) -> pd.DataFrame:
    if not 0 < development_fraction < 1:
        raise ValueError("development_fraction must be in (0, 1)")
    development = events.iloc[: int(len(events) * development_fraction)]
    rows: list[dict[str, Any]] = []
    for size in sizes:
        windows = summarize_windows(development, size)
        complete = windows[windows["num_events"] == size]
        after_first = complete.iloc[1:]
        rows.append(
            {
                "window_size": size,
                "development_windows": len(windows),
                "median_duration_hours": complete["duration_hours"].median(),
                "p95_duration_hours": complete["duration_hours"].quantile(0.95),
                "median_unique_templates": complete["num_templates"].median(),
                "median_anomaly_ratio": complete["anomaly_ratio"].median(),
                "anomaly_free_fraction": float((complete["anomaly_ratio"] == 0).mean()),
                "median_js_divergence": complete["distribution_divergence"].median(),
                "p95_js_divergence": complete["distribution_divergence"].quantile(0.95),
                "median_new_template_rate": after_first["new_template_rate"].median(),
                "p95_new_template_rate": after_first["new_template_rate"].quantile(0.95),
            }
        )
    return pd.DataFrame(rows)


def emergence_candidates(
    events: pd.DataFrame,
    *,
    first_split: str,
    minimum_events: int = 500,
    minimum_active_windows: int = 2,
) -> pd.DataFrame:
    required = {"timestamp", "template_id", "anomaly_label", "split", "window_id"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Candidate input is missing columns: {sorted(missing)}")
    chronological = events.sort_values("timestamp", kind="stable")
    first = chronological.drop_duplicates("template_id")[["template_id", "split"]].rename(
        columns={"split": "first_split"}
    )
    summary = events.groupby("template_id", as_index=False).agg(
        first_timestamp=("timestamp", "min"),
        total_events=("template_id", "size"),
        anomaly_events=("anomaly_label", "sum"),
        active_windows=("window_id", "nunique"),
    )
    summary = summary.merge(first, on="template_id")
    candidates = summary[
        (summary["first_split"] == first_split)
        & (summary["anomaly_events"] == 0)
        & (summary["total_events"] >= minimum_events)
        & (summary["active_windows"] >= minimum_active_windows)
    ].sort_values(["first_timestamp", "template_id"], kind="stable")
    candidates = candidates.reset_index(drop=True)
    candidates.insert(0, "selection_rank", np.arange(1, len(candidates) + 1))
    return candidates


def run_bgl_eda(
    events_path: str | Path,
    output_dir: str | Path,
    *,
    selected_window_size: int = 10_000,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    events = read_table(events_path).sort_values("timestamp", kind="stable").reset_index(drop=True)
    window_comparison = compare_window_sizes(events)
    windows = summarize_windows(events, selected_window_size)
    split_summary = (
        events.groupby("split", sort=False)
        .agg(
            start_time=("timestamp", "min"),
            end_time=("timestamp", "max"),
            num_events=("event_uid", "size"),
            num_templates=("template_id", "nunique"),
            anomaly_ratio=("anomaly_label", "mean"),
        )
        .reset_index()
    )
    validation_candidates = emergence_candidates(events, first_split="validation")
    test_candidates = emergence_candidates(events, first_split="test")
    top_templates = events["template_id"].value_counts().head(10).index
    top_frequency = (
        events[events["template_id"].isin(top_templates)]
        .groupby(["window_id", "template_id"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=top_templates, fill_value=0)
    )
    top_frequency = top_frequency.div(
        events.groupby("window_id").size().reindex(top_frequency.index), axis=0
    )

    window_comparison.to_csv(output / "window_size_comparison.csv", index=False)
    windows.to_csv(output / "window_metrics.csv", index=False)
    split_summary.to_csv(output / "split_summary.csv", index=False)
    validation_candidates.to_csv(output / "emergence_candidates_validation.csv", index=False)
    test_candidates.to_csv(output / "emergence_candidates_test.csv", index=False)
    top_frequency.to_csv(output / "top_template_frequency.csv")
    _write_eda_figures(windows, top_frequency, output)

    selected_validation = validation_candidates.head(5)["template_id"].tolist()
    selected_test = test_candidates.head(5)["template_id"].tolist()
    summary: dict[str, Any] = {
        "total_events": len(events),
        "selected_window_size": selected_window_size,
        "num_windows": len(windows),
        "split_summary": split_summary.to_dict(orient="records"),
        "heldout_selection_rule": {
            "minimum_events": 500,
            "minimum_active_windows": 2,
            "anomaly_events": 0,
            "ordering": "first_timestamp_then_template_id",
            "take_first": 5,
        },
        "validation_heldout_templates": selected_validation,
        "test_heldout_templates": selected_test,
    }
    write_json(summary, output / "eda_summary.json")
    return summary


def _write_eda_figures(windows: pd.DataFrame, top_frequency: pd.DataFrame, output: Path) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    series = [
        ("num_templates", "Templates per window"),
        ("new_template_rate", "New-template event rate"),
        ("anomaly_ratio", "Anomaly ratio"),
        ("distribution_divergence", "JS divergence from previous window"),
    ]
    for axis, (column, label) in zip(axes, series, strict=True):
        axis.plot(windows["window_id"], windows[column], linewidth=0.9)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("Window ID")
    figure.tight_layout()
    figure.savefig(output / "temporal_signals.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(12, 5))
    image = axis.imshow(
        top_frequency.T.to_numpy(),
        aspect="auto",
        interpolation="nearest",
        cmap="viridis",
        extent=(
            float(top_frequency.index.min()),
            float(top_frequency.index.max()),
            len(top_frequency.columns) - 0.5,
            -0.5,
        ),
    )
    axis.set_xlabel("Window ID")
    axis.set_ylabel("Template ID")
    axis.set_yticks(range(len(top_frequency.columns)))
    axis.set_yticklabels([str(value) for value in top_frequency.columns], fontsize=8)
    colorbar = figure.colorbar(image, ax=axis, pad=0.01)
    colorbar.set_label("Within-window frequency")
    figure.tight_layout()
    figure.savefig(output / "top_template_frequency.png", dpi=180)
    plt.close(figure)
