# NETDEFY Benchmark Datasets

This directory holds the generated reproducible benchmarks for NETDEFY model training and evaluation.

- `v1/`: Phase 3.2 200,000-record benchmark partitioned into:
  - `oneclass_train.parquet` (100k Monday BENIGN)
  - `classifier_train.parquet` (30k Tue/Wed)
  - `validation.parquet` (20k Tue/Wed disjoint)
  - `test.parquet` (50k Thu/Fri chronological holdout)
  - `supplementary/rare_class_diagnostic.parquet` (6,193 rare attack flows + matched BENIGN)
  - `metadata/`: Provenance, schema, config, checksums, and ambiguity manifests.

To regenerate the benchmark:
```bash
python scripts/create_benchmark.py --processed-dir data/processed --output-dir data/benchmark/v1 --seed 42
```
To validate the benchmark:
```bash
python scripts/validate_benchmark.py --benchmark-dir data/benchmark/v1
```

