---
name: qa-pipeline
description: QA Engineer skill for PixelStream. Runs the full test suite, validates each pipeline stage, checks for regressions, and reports coverage gaps. Use after any significant code change or before shipping.
---

# QA Pipeline — PixelStream

Full quality assurance sweep for PixelStream. Runs tests in order from fast to slow,
reports gaps, and blocks ship until all critical checks pass.

## Test Categories

### 1. Fast Unit Tests (mock backend, no Kafka/Spark)
```bash
uv run pytest tests/ -m "not integration" -v --tb=short
```
Expected: all pass in < 10s. These must ALWAYS pass.

Key tests:
- `test_inference.py::test_mock_backend_returns_detections`
- `test_inference.py::test_ultralytics_backend_cpu_device` (CPU assertion)
- `test_producer.py::test_frame_encoding_size` (< 50KB per frame)
- `test_schemas.py::test_detection_result_serialization`
- `test_delta_writer.py::test_write_detection_result`

### 2. Integration Tests (requires Redpanda running)
```bash
docker-compose ps | grep -q "running" && \
  uv run pytest tests/ -m "integration" -v --tb=short || \
  echo "SKIP: Redpanda not running"
```

### 3. Type Check
```bash
uv run mypy src/ --ignore-missing-imports --no-error-summary
```
Zero errors required before ship.

### 4. Lint
```bash
uv run ruff check src/ tests/
```
Zero errors required.

## Pipeline Stage Verification

After running tests, manually verify each stage:

### Stage 1: Inference Backend
```python
# Run interactively:
from pixelstream.inference.mock import MockBackend
b = MockBackend()
result = b.detect(b"fake_jpeg_bytes")
assert len(result) > 0
assert all(0 <= d.confidence <= 1 for d in result)
assert all(len(d.bbox) == 4 for d in result)
print(f"✓ MockBackend: {len(result)} detections")
```

### Stage 2: Frame Encoding
```python
import cv2, numpy as np
from pixelstream.producer.frame_producer import encode_frame
frame = np.zeros((480, 640, 3), dtype=np.uint8)
jpeg_bytes = encode_frame(frame)
assert len(jpeg_bytes) < 50_000, f"Frame too large: {len(jpeg_bytes)} bytes"
print(f"✓ Frame encoding: {len(jpeg_bytes)} bytes")
```

### Stage 3: Schema Round-Trip
```python
from pixelstream.schemas import DetectionResult, Detection
dr = DetectionResult(
    frame_id="test-123",
    timestamp=1.0,
    model="yolov11n",
    latency_ms=45.0,
    detections=[Detection(cls="person", confidence=0.91, bbox=[0.1, 0.1, 0.4, 0.6])]
)
json_str = dr.model_dump_json()
dr2 = DetectionResult.model_validate_json(json_str)
assert dr.frame_id == dr2.frame_id
print("✓ Schema round-trip OK")
```

### Stage 4: Delta Lake Write
```python
from pixelstream.storage.delta_writer import DeltaWriter
# Requires SparkSession — use conftest.py fixture
# Write 5 DetectionResults and verify count
```

### Stage 5: WebSocket API
```bash
# Start API: uv run pixelstream-api &
curl -s localhost:8000/api/stats | python3 -c "import json,sys; d=json.load(sys.stdin); print('✓ Stats:', d['total_frames'], 'frames')"
curl -s -X POST localhost:8000/api/model -H 'Content-Type: application/json' \
     -d '{"model":"rtdetr-l"}' | python3 -c "import json,sys; print('✓ Model switch:', json.load(sys.stdin))"
```

## Coverage Gaps to Check

Before shipping, verify these edge cases are tested:
- [ ] Empty Kafka micro-batch (no frames) — Spark should no-op, not error
- [ ] Model switch mid-batch — in-flight frames use old model, next batch uses new
- [ ] Video file loop — producer restarts from frame 0, frame_ids remain unique
- [ ] WebSocket reconnect — client disconnects and reconnects, stream resumes

## Report Format

After running all checks, output:
```
=== PixelStream QA Report ===

Unit tests:       X/Y passed
Integration:      X/Y passed (or SKIPPED — Redpanda not running)
Type check:       PASS / FAIL (N errors)
Lint:             PASS / FAIL (N errors)

Stage checks:
  ✓ Inference backend (mock + ultralytics)
  ✓ Frame encoding size (< 50KB)
  ✓ Schema round-trip
  ✓/✗ Delta Lake write
  ✓/✗ API stats endpoint
  ✓/✗ Model hot-swap

Coverage gaps: [list any untested edges]

VERDICT: SHIP READY ✓ / BLOCKED (reasons)
```

## Invoke data-engineer checks
After QA pipeline, also run `/data-pipeline-check` to validate data integrity
through Kafka → Spark → Delta.
