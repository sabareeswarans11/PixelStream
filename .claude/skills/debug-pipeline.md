---
name: debug-pipeline
description: Debug PixelStream pipeline issues. Use when frames are not flowing, detections are missing, Spark errors occur, WebSocket disconnects, or Delta writes fail. Systematic diagnosis from infra → Kafka → Spark → inference → API → frontend.
---

# Debug Pipeline — PixelStream

Systematic debugging from infrastructure outward. Always start at the bottom layer
and work up — don't fix the dashboard when Redpanda isn't running.

## Layer 0: Infrastructure
```bash
docker-compose ps              # are all services "running"?
docker-compose logs redpanda   # Redpanda startup errors?
lsof -i :19092                 # port in use?
lsof -i :8000                  # FastAPI port conflict?
lsof -i :5173                  # Vite port conflict?
```

## Layer 1: Redpanda / Kafka
```bash
# Topics exist?
docker exec -it $(docker-compose ps -q redpanda) rpk topic list --brokers localhost:9092

# Messages arriving?
docker exec -it $(docker-compose ps -q redpanda) \
  rpk topic consume ps.frames --brokers localhost:9092 --num 1 --format json

# Consumer lag?
docker exec -it $(docker-compose ps -q redpanda) \
  rpk group describe pixelstream-spark --brokers localhost:9092
```

**Common issues:**
- Producer connects but no messages → check `KAFKA_BOOTSTRAP=localhost:19092` (host port, not internal 9092)
- "Topic not found" → create topics: `rpk topic create ps.frames ps.detections`
- Redpanda Console shows no data → topic retention may have expired (default 1 day)

## Layer 2: Frame Producer
```bash
# Run producer with verbose logging
STRUCTLOG_LEVEL=debug uv run pixelstream-producer 2>&1 | head -30
```
Expected per frame: `event="published" topic="ps.frames" frame_id="..." size_bytes=...`

**Common issues:**
- Video file not found → check `VIDEO_SOURCE` in `.env`, run `scripts/download_video.sh`
- JPEG encode error → verify OpenCV headless: `uv run python -c "import cv2; print(cv2.__version__)"`
- Frame too large → check resize to 640×480 before encode; JPEG quality=80

## Layer 3: Spark Consumer
```bash
# Run Spark with debug logging
uv run pixelstream-spark 2>&1 | grep -E "(ERROR|WARN|StreamingQuery|batch)" | head -50
```

**Common issues:**
- Ivy2 download hanging → first run downloads ~200MB from Maven; be patient
- `kafka-clients` ClassNotFoundError → Spark jars not matching; check `spark.jars.packages` version
- `delta` ClassNotFoundError → delta-spark version must match Spark version: 3.5.x → delta-spark 3.2.x
- `foreachBatch` crashing → exception in batch_handler; look for full traceback in Spark logs
- Empty batches → producer not publishing; fix Layer 2 first

Silence noisy Spark logs:
```python
spark.sparkContext.setLogLevel("ERROR")  # in stream_processor.py
```

## Layer 4: Inference
```python
# Test inference standalone
from pixelstream.inference.ultralytics_backend import UltralyticsBackend
b = UltralyticsBackend("yolov11n")
import numpy as np
frame = np.zeros((480, 640, 3), dtype=np.uint8)
import cv2; _, jpg = cv2.imencode(".jpg", frame)
results = b.detect(jpg.tobytes())
print(results)
```
**Common issues:**
- `device='mps'` error → check `INFERENCE_DEVICE=cpu` in .env; NEVER use mps on this machine
- Model download failure → check internet, try manual download
- `numpy` version error → ultralytics requires `numpy<2.0`; check `uv run pip show numpy`

## Layer 5: Delta Writer
```bash
ls -la data/detections/        # Parquet files should appear after first Spark batch
```
**Common issues:**
- Permission error → `data/` must be writable; `chmod 755 data/`
- Schema evolution error → Delta schema changed; delete `data/detections/` and restart

## Layer 6: FastAPI / WebSocket
```bash
# Verify API is up
curl -v localhost:8000/api/stats

# WS test with wscat (install: npm i -g wscat)
wscat -c ws://localhost:8000/ws/detections
# Should stream JSON lines as detections arrive
```
**Common issues:**
- WS connects but no messages → broadcaster not consuming `ps.detections`; check Kafka consumer in api.py
- CORS error → FastAPI missing `CORSMiddleware`; add `allow_origins=["http://localhost:5173"]`
- `/api/model` 422 → body must be `{"model": "yolov11n"}` not `model=yolov11n`

## Layer 7: React Dashboard
```bash
cd dashboard && npm run dev 2>&1 | head -20
# Open browser console (Cmd+Option+J)
```
**Common issues:**
- Vite proxy not forwarding WS → check `vite.config.js` has `ws: true` in WS proxy
- Canvas not updating → check `useEffect` deps include `lastMessage`
- Chart not rendering → Visx needs a container with explicit width; use `ParentSize`
- Tailwind classes missing → check `content` in `tailwind.config.js` covers `./src/**/*.jsx`

## Escalation Path

If all layers are clean but data still doesn't reach the dashboard:
1. Add a sentinel: have `batch_handler.py` write a known test record to `ps.detections`
2. Verify broadcaster picks it up: add `print("BROADCAST:", msg)` in broadcaster.py
3. Verify WS client receives it: `wscat -c ws://localhost:8000/ws/detections`
4. Verify React state updates: add `console.log("WS MESSAGE:", lastMessage)` in App.jsx

Bisect: if it works end-to-end but React doesn't update — React bug. If ws delivers but Spark doesn't write — Spark bug. Etc.
