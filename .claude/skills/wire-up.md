---
name: wire-up
description: Wires all PixelStream components together and runs the end-to-end demo. Use after backend and frontend are built individually. Starts Redpanda → Spark consumer → frame producer → FastAPI API → React dashboard in the correct order, then verifies the full data flow.
---

# Wire Up — PixelStream End-to-End

Connects all components and runs the live demo. Run this after `/build-backend` and
`/build-frontend` are complete.

## Prerequisites Checklist
- [ ] `docker-compose up -d` — Redpanda running on `localhost:19092`
- [ ] `uv sync` — Python deps installed
- [ ] `data/sample.mp4` exists (run `scripts/download_video.sh`)
- [ ] Models downloaded (run `/download-models` or `scripts/download_models.py`)
- [ ] `cd dashboard && npm install` — Node deps installed
- [ ] `.env` exists (copy from `.env.template`)

## Startup Sequence (4 terminals)

### Terminal 1 — Infrastructure
```bash
docker-compose up -d
# Verify:
docker-compose ps   # redpanda must show "running"
# Check topics exist (create if not):
docker exec -it $(docker-compose ps -q redpanda) rpk topic create ps.frames ps.detections --brokers localhost:9092
```

### Terminal 2 — Spark Consumer (start before producer)
```bash
uv run pixelstream-spark
# Wait for: "StreamingQuery started" before moving on
# Expected: processes micro-batches every 5s, logs detection count
```

### Terminal 3 — Frame Producer
```bash
uv run pixelstream-producer
# Expected: "Publishing frame <uuid> to ps.frames" at ~5 FPS
# Verify in Redpanda Console → Topics → ps.frames → Messages
```

### Terminal 4 — Dashboard API
```bash
uv run pixelstream-api
# Then in a 5th terminal or browser:
curl http://localhost:8000/api/stats     # should return JSON
```

### Terminal 5 — React Dev Server
```bash
cd dashboard && npm run dev
# Open http://localhost:5173
```

## Verification Checklist

### Data Flow
- [ ] Redpanda Console at `http://localhost:8080` shows messages in `ps.frames`
- [ ] After 5-10s: messages appear in `ps.detections`
- [ ] Delta files written to `data/detections/` (run `ls data/detections/`)
- [ ] `curl localhost:8000/api/stats` returns `{"total_frames": N, ...}`

### Dashboard
- [ ] Green connection indicator in header
- [ ] Stats panel shows non-zero FPS and detection count
- [ ] Detection chart populates over time
- [ ] Model toggle fires POST and Spark switches model within 10s
- [ ] Browser console: zero errors

### Model Switch Test
```bash
curl -X POST localhost:8000/api/model -H "Content-Type: application/json" \
  -d '{"model": "rtdetr-l"}'
# Then watch Spark logs — should show "Switching to rtdetr-l"
# Switch back: curl -X POST localhost:8000/api/model -d '{"model": "yolov11n"}'
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Spark won't start | Ivy2 jars not downloaded | First run downloads ~200MB, wait |
| No messages in ps.frames | Producer can't connect | Check `KAFKA_BOOTSTRAP=localhost:19092` in .env |
| Dashboard WS disconnects | FastAPI not reading ps.detections | Check broadcaster.py consuming correct topic |
| RT-DETR very slow | Expected — ~3 FPS on CPU | Normal, reduce producer FPS or use mock |
| Delta write errors | Spark Delta jars version mismatch | Verify delta-spark matches spark version |

## run_demo.sh (all-in-one)
```bash
#!/bin/bash
set -e
docker-compose up -d
sleep 3
uv run python scripts/download_models.py
uv run python scripts/download_video.sh

# Background processes
uv run pixelstream-spark &
SPARK_PID=$!
sleep 10  # wait for Spark init

uv run pixelstream-producer &
PROD_PID=$!

uv run pixelstream-api &
API_PID=$!

cd dashboard && npm run dev &
DASH_PID=$!

echo "✓ PixelStream running"
echo "  Dashboard: http://localhost:5173"
echo "  Redpanda Console: http://localhost:8080"
echo "  API stats: http://localhost:8000/api/stats"
echo "  Press Ctrl+C to stop all"

trap "kill $SPARK_PID $PROD_PID $API_PID $DASH_PID 2>/dev/null; docker-compose down" EXIT
wait
```

## After Successful Demo
Run `/qa-pipeline` then `/ship-pixelstream` to push to GitHub.
