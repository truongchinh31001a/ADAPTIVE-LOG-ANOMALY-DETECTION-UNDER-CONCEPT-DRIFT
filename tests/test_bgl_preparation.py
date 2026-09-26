from pathlib import Path

from adaptive_lad.data.bgl import prepare_bgl


def test_prepare_raw_bgl_keeps_windows_inside_one_split(tmp_path: Path) -> None:
    source = tmp_path / "BGL.log"
    source.write_text(
        "\n".join(
            [
                f"- {1117838570 + index} 2005.06.03 R02-M1-N0 "
                f"2005-06-03-15.42.50 R02-M1-N0 RAS KERNEL INFO heartbeat {index}"
                for index in range(12)
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "events.parquet"
    events = prepare_bgl(
        source,
        output,
        window_size=3,
        train_fraction=0.25,
        validation_fraction=0.25,
    )
    assert output.exists()
    assert len(events) == 12
    assert events.groupby("window_id")["split"].nunique().max() == 1
    assert set(events["split"]) == {"train", "validation", "test"}
    assert events["template_id"].nunique() == 1
    assert events["template_id"].iloc[0].startswith("D")
    assert events["parsed_message"].iloc[-1] == "heartbeat <*>"


def test_regex_parser_remains_available_as_sensitivity_baseline(tmp_path: Path) -> None:
    source = tmp_path / "BGL.log"
    source.write_text(
        "- 1117838570 2005.06.03 R02-M1-N0 2005-06-03-15.42.50 "
        "R02-M1-N0 RAS KERNEL INFO heartbeat 42\n",
        encoding="utf-8",
    )

    events = prepare_bgl(
        source,
        tmp_path / "events.parquet",
        window_size=1,
        train_fraction=0.34,
        validation_fraction=0.33,
        parser_implementation="regex",
    )

    assert events["parsed_message"].iloc[0] == "heartbeat <*>"
    assert events["template_id"].iloc[0].startswith("E")
