# BGL parser validation

## Decision

The main parser is Drain3 0.9.11 with similarity threshold 0.40, depth 4,
`max_children` 100, and numeric token parameterization enabled. The configuration was
selected before downstream policy experiments and is frozen in `configs/data/bgl.yaml`.

## Ground-truth sample check

The official Loghub `BGL_2k.log_structured.csv` sample was processed in chronological
row order. Drain cluster assignments were compared with the supplied EventId labels.

| Similarity threshold | True templates | Drain clusters | Adjusted Rand | Homogeneity | Completeness | V-measure |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 120 | 100 | 0.9987 | 0.9818 | 1.0000 | 0.9908 |
| 0.40 | 120 | 105 | 0.9996 | 0.9896 | 1.0000 | 0.9948 |
| 0.50 | 120 | 108 | 0.9995 | 0.9898 | 0.9989 | 0.9943 |

Threshold 0.40 produced the best Adjusted Rand score and V-measure of the tested
settings. The sample check is a parser sanity test, not downstream test-set tuning.

## Chronological training-prefix stability check

The first 100,000 raw BGL records were parsed without malformed lines. This prefix is
inside the chronological training portion and was used only to compare parser behavior.

| Similarity threshold | Clusters | Singleton clusters | Singleton ratio | Template changes |
|---:|---:|---:|---:|---:|
| 0.30 | 65 | 15 | 0.2308 | 41 |
| 0.40 | 70 | 16 | 0.2286 | 38 |
| 0.50 | 70 | 16 | 0.2286 | 38 |

Thresholds 0.40 and 0.50 were identical on this prefix. The labeled sample result breaks
the tie in favor of 0.40.

## Full-data parse

- Input: 4,747,963 records, SHA-256
  `666130b15ef44eb32fd02bd053e6c6e007c37696b5e7e8b9d8e45b729876a5d2`.
- Parsed time span: 2005-06-03 22:42:50 UTC to 2006-01-04 16:00:05 UTC.
- Normal records: 4,399,503.
- Anomalous records: 348,460.
- Drain clusters: 1,823.
- Malformed/skipped records: 0.

The large tail of rare clusters must be handled explicitly during EDA. Held-out
emergence templates must be selected from normal templates with enough support and must
not be chosen merely because they are singletons created by parser fragmentation.
