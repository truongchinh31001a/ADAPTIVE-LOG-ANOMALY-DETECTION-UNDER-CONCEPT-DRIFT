# Data zones

- `bronze/`: immutable source files exactly as acquired.
- `silver/events/`: normalized event-level data.
- `silver/templates/`: template registry.
- `silver/windows/`: deterministic temporal aggregates.
- `gold/`: analysis-ready detector, drift, and adaptation tables.
- `drift_scenarios/`: generated streams and ground truth.
- `metadata/`: dataset registry, checksums, and frozen ground truth.
- `results/`: consolidated experiment outputs.

Large data is intentionally ignored by Git. Each dataset must have a registry record with
source URL/citation, acquisition date, license note, byte size, and SHA-256 checksum.

