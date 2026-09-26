import pandas as pd

from adaptive_lad.data.bgl import make_demo_events
from adaptive_lad.evaluation.eda import (
    compare_window_sizes,
    emergence_candidates,
    summarize_windows,
)


def test_window_summary_preserves_event_count_and_temporal_signals() -> None:
    events = make_demo_events(num_windows=12, window_size=20)
    events = events[~events["heldout_only"]]

    windows = summarize_windows(events, 20)

    assert len(windows) == 12
    assert windows["num_events"].sum() == len(events)
    assert windows["distribution_divergence"].iloc[0] != windows["distribution_divergence"].iloc[0]
    assert windows["distribution_divergence"].iloc[1:].notna().all()


def test_window_comparison_uses_only_development_prefix() -> None:
    events = make_demo_events(num_windows=20, window_size=20)
    events = events[~events["heldout_only"]]

    comparison = compare_window_sizes(events, sizes=(10, 20), development_fraction=0.4)

    assert comparison.set_index("window_size").loc[20, "development_windows"] == 8
    assert comparison.set_index("window_size").loc[10, "development_windows"] == 16


def test_emergence_candidates_require_later_normal_supported_templates() -> None:
    events = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC"),
            "template_id": ["A", "A", "B", "B", "B", "C", "C", "D"],
            "anomaly_label": [0, 0, 0, 0, 0, 0, 1, 0],
            "split": [
                "train",
                "train",
                "validation",
                "validation",
                "validation",
                "test",
                "test",
                "test",
            ],
            "window_id": [0, 0, 1, 2, 2, 3, 4, 4],
        }
    )

    candidates = emergence_candidates(
        events,
        first_split="validation",
        minimum_events=3,
        minimum_active_windows=2,
    )

    assert candidates["template_id"].tolist() == ["B"]
