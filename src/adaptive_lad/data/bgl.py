from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from adaptive_lad.io import write_json, write_table

_RAW_BGL_PATTERN = re.compile(
    r"^(?P<label>\S+)\s+(?P<epoch>\d+)\s+(?P<date>\S+)\s+(?P<node>\S+)\s+"
    r"(?P<time>\S+)\s+(?P<node_repeat>\S+)\s+(?P<type>\S+)\s+"
    r"(?P<component>\S+)\s+(?P<level>\S+)\s*(?P<content>.*)$"
)
_TOKEN_PATTERNS = [
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b0x[0-9a-fA-F]+\b"),
    re.compile(r"\b[0-9a-fA-F]{8,}\b"),
    re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?![A-Za-z])"),
]

EVENT_COLUMNS = [
    "event_uid",
    "timestamp",
    "dataset",
    "host",
    "component",
    "raw_message",
    "parsed_message",
    "template_id",
    "parameters",
    "anomaly_label",
    "window_id",
    "split",
]


def prepare_bgl(
    input_path: str | Path,
    output_path: str | Path,
    *,
    window_size: int = 10_000,
    train_fraction: float = 0.2,
    validation_fraction: float = 0.2,
    parser_implementation: str = "drain3",
    drain_similarity_threshold: float = 0.40,
    drain_depth: int = 4,
    drain_max_children: int = 100,
) -> pd.DataFrame:
    path = Path(input_path)
    parser_config: dict[str, Any] = {
        "implementation": parser_implementation,
        "drain3_version": "0.9.11" if parser_implementation == "drain3" else None,
        "similarity_threshold": drain_similarity_threshold,
        "depth": drain_depth,
        "max_children": drain_max_children,
    }
    if path.suffix.lower() == ".csv":
        raw = _read_structured_csv(path, parser_config=parser_config)
    else:
        raw = _read_raw_bgl(path, parser_config=parser_config)
    events = _finalize_events(
        raw,
        window_size=window_size,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    write_table(events, output_path)
    stats = dataset_stats(events)
    stats["parser"] = parser_config
    write_json(stats, Path(output_path).with_name("dataset_stats.json"))
    templates = (
        events.groupby("template_id", as_index=False)
        .agg(
            parsed_message=("parsed_message", "last"),
            frequency=("event_uid", "size"),
            anomaly_ratio=("anomaly_label", "mean"),
        )
        .sort_values("frequency", ascending=False)
    )
    write_table(templates, Path(output_path).with_name("templates.parquet"))
    return events


def normalize_template(message: str) -> tuple[str, list[str]]:
    normalized = str(message)
    parameters: list[str] = []
    for pattern in _TOKEN_PATTERNS:
        parameters.extend(pattern.findall(normalized))
        normalized = pattern.sub("<*>", normalized)
    normalized = " ".join(normalized.split())
    return normalized, parameters


def dataset_stats(events: pd.DataFrame) -> dict[str, object]:
    return {
        "dataset": str(events["dataset"].iloc[0]) if len(events) else "bgl",
        "total_logs": int(len(events)),
        "normal_logs": int((events["anomaly_label"] == 0).sum()),
        "anomalous_logs": int((events["anomaly_label"] == 1).sum()),
        "unique_templates": int(events["template_id"].nunique()),
        "first_timestamp": events["timestamp"].min(),
        "last_timestamp": events["timestamp"].max(),
        "num_windows": int(events["window_id"].nunique()),
        "template_frequencies": {
            str(key): int(value) for key, value in events["template_id"].value_counts().items()
        },
    }


def make_demo_events(seed: int = 17, num_windows: int = 25, window_size: int = 200) -> pd.DataFrame:
    """Create a deterministic smoke-test stream; never use it as research evidence."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    rows: list[dict[str, object]] = []
    normal_templates = np.array(["N1", "N2", "N3"])
    normal_probabilities = np.array([0.85, 0.14, 0.01])
    index = 0
    for window_id in range(num_windows):
        for _ in range(window_size):
            anomaly = bool(rng.random() < 0.02)
            template_id = (
                "A1" if anomaly else str(rng.choice(normal_templates, p=normal_probabilities))
            )
            message = {
                "N1": "kernel heartbeat completed",
                "N2": "job <*> scheduled on node <*> ",
                "N3": "filesystem cache was refreshed",
                "A1": "fatal machine check exception",
            }[template_id].strip()
            rows.append(
                _event_row(
                    index=index,
                    timestamp=start + pd.Timedelta(seconds=index),
                    template_id=template_id,
                    message=message,
                    anomaly=int(anomaly),
                    window_id=window_id,
                    split=_split_for_window(window_id, num_windows),
                )
            )
            index += 1

    # A separate held-out normal pool provides legitimate emergence templates.
    for template_id, message in [("E1", "new service health check"), ("E2", "new rpc route ready")]:
        for _ in range(20):
            row = _event_row(
                index=index,
                timestamp=start + pd.Timedelta(seconds=index),
                template_id=template_id,
                message=message,
                anomaly=0,
                window_id=num_windows,
                split="pool",
            )
            row["heldout_only"] = True
            rows.append(row)
            index += 1
    frame = pd.DataFrame(rows)
    frame["heldout_only"] = frame.get("heldout_only", False).fillna(False).astype(bool)
    return frame.sort_values(["timestamp", "event_uid"]).reset_index(drop=True)


def _read_structured_csv(path: Path, *, parser_config: dict[str, Any]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    content_col = _first_column(frame, "Content", "content", "raw_message")
    label_col = _first_column(frame, "Label", "label", "anomaly_label", required=False)
    event_col = _first_column(frame, "EventId", "template_id", required=False)
    template_col = _first_column(frame, "EventTemplate", "parsed_message", required=False)
    time_col = _first_column(frame, "Timestamp", "timestamp", "Time", required=False)
    host_col = _first_column(frame, "Node", "host", required=False)
    component_col = _first_column(frame, "Component", "component", required=False)
    parser = str(parser_config["implementation"])
    miner = _build_drain_miner(parser_config) if parser == "drain3" else None
    rows = []
    for position, row in frame.iterrows():
        raw_message = str(row[content_col])
        if parser == "drain3":
            assert miner is not None
            parsed, template_id, parameters = _drain_template(miner, raw_message)
        elif parser == "structured":
            normalized, parameters = normalize_template(raw_message)
            parsed = str(row[template_col]) if template_col else normalized
            template_id = str(row[event_col]) if event_col else _template_hash(parsed)
        elif parser == "regex":
            parsed, parameters = normalize_template(raw_message)
            template_id = _template_hash(parsed)
        else:
            raise ValueError(f"Unsupported parser implementation: {parser}")
        timestamp = _coerce_timestamp(row[time_col] if time_col else position)
        label = row[label_col] if label_col else "-"
        rows.append(
            {
                "timestamp": timestamp,
                "host": str(row[host_col]) if host_col else "",
                "component": str(row[component_col]) if component_col else "",
                "raw_message": raw_message,
                "parsed_message": parsed,
                "template_id": template_id,
                "parameters": json.dumps(parameters),
                "anomaly_label": _label_to_int(label),
            }
        )
    return pd.DataFrame(rows)


def _read_raw_bgl(path: Path, *, parser_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    malformed = 0
    parser = str(parser_config["implementation"])
    if parser == "structured":
        raise ValueError("The structured parser requires a CSV with EventId/EventTemplate columns")
    miner = _build_drain_miner(parser_config) if parser == "drain3" else None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            match = _RAW_BGL_PATTERN.match(line.rstrip("\n"))
            if not match:
                malformed += 1
                continue
            fields = match.groupdict()
            if parser == "drain3":
                assert miner is not None
                parsed, template_id, parameters = _drain_template(miner, fields["content"])
            elif parser == "regex":
                parsed, parameters = normalize_template(fields["content"])
                template_id = _template_hash(parsed)
            else:
                raise ValueError(f"Unsupported parser implementation: {parser}")
            rows.append(
                {
                    "timestamp": pd.to_datetime(int(fields["epoch"]), unit="s", utc=True),
                    "host": fields["node"],
                    "component": fields["component"],
                    "raw_message": fields["content"],
                    "parsed_message": parsed,
                    "template_id": template_id,
                    "parameters": json.dumps(parameters),
                    "anomaly_label": _label_to_int(fields["label"]),
                    "source_line": line_number,
                }
            )
    if not rows:
        raise ValueError(f"No BGL records could be parsed from {path}")
    if malformed:
        print(f"Warning: skipped {malformed} malformed BGL lines")
    return pd.DataFrame(rows)


def _build_drain_miner(parser_config: dict[str, Any]) -> TemplateMiner:
    similarity_threshold = float(parser_config["similarity_threshold"])
    depth = int(parser_config["depth"])
    max_children = int(parser_config["max_children"])
    if not 0 < similarity_threshold <= 1:
        raise ValueError("Drain similarity threshold must be in (0, 1]")
    if depth < 3 or max_children <= 0:
        raise ValueError("Drain depth must be at least 3 and max_children must be positive")
    config = TemplateMinerConfig()
    config.drain_sim_th = similarity_threshold
    config.drain_depth = depth
    config.drain_max_children = max_children
    config.parametrize_numeric_tokens = True
    config.profiling_enabled = False
    return TemplateMiner(config=config)


def _drain_template(miner: TemplateMiner, message: str) -> tuple[str, str, list[str]]:
    result: dict[str, Any] = miner.add_log_message(str(message))
    template = str(result["template_mined"])
    cluster_id = int(result["cluster_id"])
    parameters = [
        str(parameter.value) for parameter in miner.extract_parameters(template, str(message))
    ]
    return template, f"D{cluster_id:08d}", parameters


def _finalize_events(
    raw: pd.DataFrame,
    *,
    window_size: int,
    train_fraction: float,
    validation_fraction: float,
) -> pd.DataFrame:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if train_fraction <= 0 or validation_fraction < 0 or train_fraction + validation_fraction >= 1:
        raise ValueError("Invalid chronological split fractions")
    frame = raw.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["dataset"] = "bgl"
    frame["event_uid"] = [f"bgl-{index:09d}" for index in range(len(frame))]
    frame["window_id"] = np.arange(len(frame), dtype=np.int64) // window_size
    num_windows = int(frame["window_id"].max()) + 1
    train_window_count = max(1, int(num_windows * train_fraction))
    validation_window_count = max(1, int(num_windows * validation_fraction))
    validation_start = train_window_count
    test_start = min(num_windows, validation_start + validation_window_count)
    frame["split"] = "test"
    frame.loc[frame["window_id"] < validation_start, "split"] = "train"
    frame.loc[
        (frame["window_id"] >= validation_start) & (frame["window_id"] < test_start),
        "split",
    ] = "validation"
    frame["anomaly_label"] = frame["anomaly_label"].astype("int8")
    return frame[EVENT_COLUMNS]


def _event_row(
    *,
    index: int,
    timestamp: pd.Timestamp,
    template_id: str,
    message: str,
    anomaly: int,
    window_id: int,
    split: str,
) -> dict[str, object]:
    return {
        "event_uid": f"demo-{index:07d}",
        "timestamp": timestamp,
        "dataset": "demo",
        "host": "node-1",
        "component": "demo",
        "raw_message": message,
        "parsed_message": message,
        "template_id": template_id,
        "parameters": "[]",
        "anomaly_label": anomaly,
        "window_id": window_id,
        "split": split,
        "heldout_only": False,
    }


def _split_for_window(window_id: int, total: int) -> str:
    if window_id < int(total * 0.2):
        return "train"
    if window_id < int(total * 0.4):
        return "validation"
    return "test"


def _template_hash(template: str) -> str:
    return f"E{hashlib.sha1(template.encode('utf-8')).hexdigest()[:8]}"


def _label_to_int(value: object) -> int:
    return int(str(value).strip().lower() not in {"-", "0", "normal", "false", "nan", ""})


def _coerce_timestamp(value: object) -> pd.Timestamp:
    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
        unit = "us" if numeric > 1e14 else "ms" if numeric > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, utc=True)
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Cannot parse timestamp: {value}")
    return parsed


def _first_column(frame: pd.DataFrame, *candidates: str, required: bool = True) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    if required:
        raise ValueError(f"Missing one of required columns: {candidates}")
    return None
