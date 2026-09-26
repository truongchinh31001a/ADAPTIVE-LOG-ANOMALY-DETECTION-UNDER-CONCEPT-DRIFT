from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from adaptive_lad.experiments.batch import summarize_results
from adaptive_lad.io import sha256_file, write_json, write_table


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge and summarize completed experiment batches")
    parser.add_argument("inputs", nargs="+", type=Path, help="CSV files or batch directories")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--replace-duplicates",
        action="store_true",
        help="Keep the last input for duplicate run keys (for audited bug-fix reruns)",
    )
    args = parser.parse_args()

    source_paths = [path / "results_raw.csv" if path.is_dir() else path for path in args.inputs]
    frames = [pd.read_csv(path) for path in source_paths]
    results = pd.concat(frames, ignore_index=True)
    duplicate_keys = ["phase", "scenario_id", "seed", "drift_magnitude", "method"]
    duplicated = results.duplicated(duplicate_keys, keep=False)
    if duplicated.any():
        if args.replace_duplicates:
            results = results.drop_duplicates(duplicate_keys, keep="last")
        else:
            examples = results.loc[duplicated, duplicate_keys].head().to_dict("records")
            raise ValueError(f"Duplicate experimental runs found: {examples}")

    args.output.mkdir(parents=True, exist_ok=True)
    results = results.sort_values(duplicate_keys).reset_index(drop=True)
    write_table(results, args.output / "results_raw.parquet")
    results.to_csv(args.output / "results_raw.csv", index=False)
    summarize_results(results).to_csv(args.output / "summary.csv", index=False)
    write_json(
        {
            "source_files": [str(path.resolve()) for path in source_paths],
            "source_sha256": {str(path.resolve()): sha256_file(path) for path in source_paths},
            "run_count": len(results),
            "seeds": sorted(int(value) for value in results["seed"].unique()),
            "replace_duplicates": args.replace_duplicates,
        },
        args.output / "merge_manifest.json",
    )
    print(f"Merged {len(results)} runs -> {args.output}")


if __name__ == "__main__":
    main()
