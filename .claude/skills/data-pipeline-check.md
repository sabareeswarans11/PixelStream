---
name: data-pipeline-check
description: Data Engineer skill for PixelStream. Validates data integrity, schema consistency, Kafka topic health, Delta Lake table quality, and end-to-end message flow. Use at each pipeline stage milestone and before shipping.
---

# Data Pipeline Check — PixelStream

You are a Data Engineer validating PixelStream's data pipeline. Check schema,
message integrity, topic health, and Delta Lake quality at each stage.

## Pre-check: Infrastructure Health
```bash
# Redpanda must be running
docker-compose ps | grep redpanda
# Topics must exist
docker exec -it $(docker-compose ps -q redpanda) rpk topic list --brokers localhost:9092
# Expected topics: ps.frames, ps.detections
```

## Check 1: Kafka Topic Schema Validation

Sample 5 messages from `ps.frames` and validate FrameMessage schema:
```bash
docker exec -it $(docker-compose ps -q redpanda) \
  rpk topic consume ps.frames --brokers localhost:9092 --num 5 --format json
```
Validate each message has: `frame_id`, `timestamp`, `source_id`, `frame_b64`, `width=640`, `height=480`.
Frame size decoded from base64 should be < 50KB.

Sample from `ps.detections`:
```bash
docker exec -it $(docker-compose ps -q redpanda) \
  rpk topic consume ps.detections --brokers localhost:9092 --num 5 --format json
```
Validate: `frame_id`, `timestamp`, `model`, `latency_ms`, `detections[]` with `cls`, `confidence` (0-1), `bbox` ([x1,y1,x2,y2] normalized 0-1).

## Check 2: Message Latency
`ps.detections.timestamp - ps.frames.timestamp` = end-to-end latency.
Expected: < 2000ms (2 seconds) for YOLOv11n on CPU.
Warning if > 5000ms.

## Check 3: Frame ID Uniqueness
```python
# Pull 100 frame_ids from ps.frames
# Assert all unique (no loops causing duplicate IDs)
ids = [msg["frame_id"] for msg in consume_n("ps.frames", 100)]
assert len(ids) == len(set(ids)), f"DUPLICATE FRAME IDs: {len(ids) - len(set(ids))} dupes"
```

## Check 4: Delta Lake Table Quality
```python
from delta import DeltaTable
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("DataCheck") \
    .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.2.0") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

df = spark.read.format("delta").load("data/detections")

# Schema check
expected_cols = {"frame_id", "timestamp", "model", "latency_ms", "detections"}
actual_cols = set(df.columns)
assert expected_cols == actual_cols, f"Schema mismatch: {actual_cols - expected_cols}"

# Null check
for col in ["frame_id", "timestamp", "model"]:
    null_count = df.filter(df[col].isNull()).count()
    assert null_count == 0, f"NULL values in {col}: {null_count}"

# Confidence range check
from pyspark.sql.functions import explode, col
detections_df = df.select(explode("detections").alias("det"))
out_of_range = detections_df.filter(
    (col("det.confidence") < 0) | (col("det.confidence") > 1)
).count()
assert out_of_range == 0, f"Confidence out of [0,1]: {out_of_range} rows"

# BBox normalization check
bbox_check = detections_df.filter(
    (col("det.bbox")[0] < 0) | (col("det.bbox")[2] > 1)
).count()
assert bbox_check == 0, f"BBox not normalized: {bbox_check} rows"

print(f"✓ Delta table: {df.count()} rows, schema valid, no nulls, confidence in range")
```

## Check 5: Throughput Accounting
```python
# Producer FPS vs. Spark batch rate
# If producer pushes at 5 FPS and batch interval is 5s:
# Each micro-batch should contain ~25 frames
# If consistently < 10 frames/batch: producer may be too slow or Kafka lag building
```
Check Redpanda Console → Consumer Groups → `pixelstream-spark` → lag per partition.
Acceptable lag: < 50 messages. If lag grows: Spark is falling behind, reduce producer FPS.

## Check 6: Model Label Consistency
```python
# All 'model' values in Delta should be one of the known models
valid_models = {"yolov11n", "rtdetr-l", "mock"}
models_in_delta = {row.model for row in df.select("model").distinct().collect()}
unknown = models_in_delta - valid_models
assert not unknown, f"Unknown model labels in Delta: {unknown}"
```

## Data Quality Report
```
=== PixelStream Data Pipeline Report ===

Infrastructure:
  Redpanda:      ✓/✗ running
  Topics:        ps.frames (N msgs), ps.detections (N msgs)

Schema Validation:
  ps.frames:     ✓/✗ valid FrameMessage schema
  ps.detections: ✓/✗ valid DetectionResult schema

Data Integrity:
  Frame ID uniqueness:   ✓/✗ (N dupes if any)
  E2E latency:           avg Xms / max Yms
  Kafka consumer lag:    N messages

Delta Lake:
  Row count:     N
  Schema:        ✓/✗
  Null checks:   ✓/✗
  Confidence:    ✓/✗ all in [0,1]
  BBox:          ✓/✗ all normalized
  Model labels:  {yolov11n: N, rtdetr-l: N}

VERDICT: DATA CLEAN ✓ / ISSUES FOUND (details above)
```

## When to run
- After first successful Spark micro-batch
- After implementing real `UltralyticsBackend` (verify confidence values are real, not mock)
- After model switch (verify model label changes in Delta)
- Before `/ship-pixelstream`
