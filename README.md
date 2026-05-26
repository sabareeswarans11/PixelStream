# PixelStream

**Real-time streaming computer vision pipeline — Kafka → Spark → ONNX inference → React dashboard**

> The reference implementation that blog posts describe but nobody publishes. PixelStream is a fully working, single-machine demo of the canonical ML streaming architecture: ingest video frames into Kafka, process with Spark Structured Streaming, run object detection with YOLOv11n or RT-DETR-l, persist to Delta Lake, and stream annotated results to a live React dashboard — all on CPU, no cloud, no GPU required.

---

## Demo

<!-- Replace with your screen recording once captured -->
> 📹 **`pixelstream_demo.gif`** — drop your screen recording here
>
> Suggested: record `http://localhost:5173` with auto-detect ON, switch between models, then switch to the live webcam stream.

![Demo placeholder](https://placehold.co/900x500/1a1a2e/7c3aed?text=PixelStream+Demo)

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────────────────────┐     ┌────────────┐
│  Video Source   │────▶│    Kafka topic   │────▶│   Spark Structured Streaming     │────▶│ Delta Lake │
│  (file / HLS /  │     │   ps.frames      │     │   local[*] — foreachBatch:       │     │ Parquet    │
│   webcam)       │     │                  │     │   1. decode JPEG                 │     └────────────┘
└─────────────────┘     │   ps.detections  │◀────│   2. ONNX Runtime inference      │
       ▲                └──────────────────┘     │   3. write → Delta Lake          │
       │                                         │   4. publish → ps.detections     │
FrameProducer                                    └──────────────────────────────────┘
(Python process)                                               │
                                                     FastAPI WebSocket /ws/detections
                                                               │
                                                   ┌───────────────────────┐
                                                   │    React Dashboard    │
                                                   │  ┌─────────────────┐  │
                                                   │  │  Video + BBox   │  │
                                                   │  │  overlay canvas │  │
                                                   │  ├─────────────────┤  │
                                                   │  │  Latency chart  │  │
                                                   │  │  Class bar chart│  │
                                                   │  │  Detection feed │  │
                                                   │  └─────────────────┘  │
                                                   └───────────────────────┘
```

### Data flow detail

| Stage | Transport | Format | Rate |
|---|---|---|---|
| FrameProducer → Kafka | `confluent-kafka` | `{frame_id, timestamp, frame_b64 (JPEG/Base64), 640×480}` | 5 FPS |
| Kafka → Spark | Spark `readStream` Kafka connector | Raw JSON bytes | streaming |
| Spark → ONNX | in-process `foreachBatch` | numpy `uint8` array | per micro-batch (5 s) |
| ONNX → Delta Lake | `delta-spark` write | Parquet partitioned by `dt=YYYY-MM-DD` | per batch |
| Spark → WebSocket | Kafka `ps.detections` → FastAPI broadcaster | `DetectionResult` JSON | per detection |
| FastAPI → Browser | WebSocket text frames | `{frame_id, model, latency_ms, detections[{cls, confidence, bbox}]}` | streaming |

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Package manager | **uv** | Lock-file reproducibility, fast installs |
| Message bus | **Apache Kafka 3.8.1 (KRaft)** | No ZooKeeper, single binary, self-contained |
| Stream processing | **PySpark 3.5 + Delta Lake 3.2** | Industry-standard; `local[*]` needs no cluster |
| Inference | **ONNX Runtime 1.18.0** | Cross-platform CPU inference; avoids PyTorch wheel gaps on Intel Mac |
| Models | **YOLOv11n + RT-DETR-l** (Ultralytics, MIT) | Both COCO-pretrained, auto-exported to ONNX on first run |
| API | **FastAPI + Uvicorn** | Async WebSocket + REST in one process |
| Dashboard | **React 19 + Vite + Tailwind + Visx** | `@visx` = Airbnb's typed D3 wrapper; canvas bbox overlay |
| Config | **Pydantic v2 + pydantic-settings** | Typed, env-driven — no hardcoded values |
| Logging | **structlog** | Structured JSON logs, correlates across processes |

### Why ONNX Runtime instead of PyTorch at inference time?

PyTorch does not publish wheels for Intel Mac (`x86_64`) on macOS 15+. ONNX Runtime 1.18.0 is the last release with that target and is 2–3× faster on CPU for inference anyway. Models are exported to ONNX once (via a conda env with torch 2.2.2) and then run with `ort.InferenceSession` — no PyTorch dependency at runtime.

### Model output format differences (YOLO vs RT-DETR)

Both models are exported to ONNX via `ultralytics`, but their output tensors differ:

```
YOLOv11n:   [1, 84, 8400]   →  84 = 4 (xywh pixel-space) + 80 class scores
                                  transpose → [8400, 84], argmax over scores
RT-DETR-l:  [1, 300, 6]     →  6 = [x1, y1, x2, y2, confidence, class_id]
                                  already normalized [0,1], no argmax needed
```

The `_postprocess()` method branches on `output.shape[-1] == 6` to handle both correctly.

---

## Models

| Model | File | Size | CPU speed | Notes |
|---|---|---|---|---|
| YOLOv11n | `yolo11n.pt` → `data/models/yolov11n.onnx` | ~10 MB ONNX | ~600 ms/frame | Default. Fast enough for demo at 5 FPS input |
| RT-DETR-l | `rtdetr-l.pt` → `data/models/rtdetr-l.onnx` | ~132 MB ONNX | ~2–4 s/frame | Transformer-based; more accurate on small/occluded objects |

Both auto-download from `ultralytics` on first use and auto-export to ONNX on first `detect()` call. No manual download step needed.

---

## Dashboard Features

- **Video source picker** — local presets (sample footage, aerial traffic), live HLS webcam stream, file upload, or any custom MP4/HLS URL
- **On-demand Detect** — capture the current video frame and run inference immediately; result overlaid on canvas for 4 seconds
- **Auto-detect** — toggle to run inference every ~1 s continuously; bounding boxes track moving objects; latency and class distribution charts update in real time
- **Live webcam** — Marblehead Lighthouse (Ohio) HLS stream with CORS headers; Detect works on it
- **Model hot-swap** — switch between YOLOv11n and RT-DETR-l at runtime; backend reloads on next inference
- **Latency chart** — rolling 60-point line chart of `inference_latency_ms`
- **Class bar chart** — detection count by COCO class over the last 60 results
- **Detection feed** — scrolling log of raw detection events with timestamps

---

## How This Was Built — Context Engineering

PixelStream was built using **context engineering**: authoring a detailed `CLAUDE.md` specification before writing a single line of code, then using that file as the persistent context harness that guided every development decision.

### What is context engineering?

Context engineering is the practice of writing the *context* that an AI coding assistant needs — constraints, architecture decisions, hardware limits, tech choices, coding conventions — as a structured document that lives in the repository. This is the software engineering equivalent of writing a thorough design doc before implementation, except the document is also machine-readable instruction.

The key artifacts:

```
CLAUDE.md                    ← The harness: architecture, constraints, conventions, build order
.claude/settings.json        ← Tool permissions, hooks (e.g. auto-format on write)
src/pixelstream/schemas.py   ← Shared Pydantic models — the "contract" between all components
```

### The CLAUDE.md approach

The `CLAUDE.md` in this repo encodes:

- **Hardware constraints up front** — `Intel Mac 2019, AMD Radeon — PyTorch does NOT support AMD on Intel Mac. All inference is CPU-only.` This prevented every `device="mps"` suggestion before it happened.
- **Explicit build order** — scaffold → config → inference mock → inference real → producer → spark → API → dashboard. Each layer verified before the next.
- **Architecture decisions with rationale** — why `confluent-kafka` over `kafka-python`, why `local[*]` Spark, why ONNX Runtime instead of PyTorch, why Delta Lake over raw Parquet.
- **Coding conventions** — absolute imports, Pydantic v2 `model_dump()`, `structlog` everywhere, no `print()` in production code.
- **DO NOT list** — explicit anti-patterns: `device="mps"`, `cv2.imshow()`, full-resolution WebSocket frames, `kafka-python`.

### Why this produces better results than chat-based prompting

| Chat-based prompting | Context engineering |
|---|---|
| Hardware constraints re-stated in every message | Written once in CLAUDE.md; applies to every tool call |
| Architecture choices relitigated per session | Captured as decisions with rationale; don't drift |
| Conventions enforced by correction | Enforced by specification; errors prevented, not fixed |
| No memory of what was verified | Build order in CLAUDE.md tracks what's been confirmed |
| "Make it work" pressure | "Make it work like the spec says" — explicit success criteria |

The harness is not prompting. It is specification-first engineering applied to AI-assisted development.

---

## Quick Start

### Prerequisites

- macOS (Intel or Apple Silicon) — Linux works too; adjust Kafka paths
- Python 3.11
- Node 18+
- `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Apache Kafka 3.8+ (KRaft mode — no ZooKeeper needed)
- `git`

### 1. Clone and install

```bash
git clone https://github.com/sabareeswarans11/PixelStream.git
cd PixelStream
cp .env.template .env       # defaults work out of the box
uv sync
```

### 2. Start Kafka (KRaft — no Docker needed)

```bash
# Download Kafka 3.8.1 if not installed
# https://kafka.apache.org/downloads

KAFKA_DIR=~/kafka   # adjust to your path

# Format storage (first time only)
$KAFKA_DIR/bin/kafka-storage.sh format \
  -t $($KAFKA_DIR/bin/kafka-storage.sh random-uuid) \
  -c $KAFKA_DIR/config/kraft/server.properties

# Start broker
$KAFKA_DIR/bin/kafka-server-start.sh $KAFKA_DIR/config/kraft/server.properties
```

### 3. Download sample video

```bash
bash scripts/download_video.sh
```

### 4. Export models to ONNX (one-time)

ONNX files are created automatically on first `detect()` call if you have `ultralytics` installed with a working PyTorch. If not (Intel Mac with no PyTorch wheel), use the export script with a conda env:

```bash
# Only needed if auto-export fails (no PyTorch wheel for your platform)
conda create -n px-export python=3.11 -y
conda activate px-export
pip install "torch==2.2.2" "ultralytics==8.4.54" "onnx==1.16.0"
python scripts/export_onnx.py
conda deactivate
```

### 5. Start the pipeline (4 terminals)

```bash
# Terminal 1 — Spark consumer
uv run pixelstream-spark

# Terminal 2 — Frame producer
uv run pixelstream-producer

# Terminal 3 — FastAPI + WebSocket
uv run pixelstream-api

# Terminal 4 — React dashboard
cd dashboard && npm install && npm run dev
```

Open **http://localhost:5173**

### 6. Use the dashboard

- Pick **City Traffic** or **Sample** → video plays immediately
- Click **⚡ Auto-detect** → inference runs every ~1 s, charts fill up
- Switch model via the **YOLOv11n / RT-DETR** toggle (bottom left)
- Click **🔴 Marblehead Live** → live HLS webcam stream from Ohio

---

## Configuration

All config is in `.env` (never committed):

```bash
KAFKA_BOOTSTRAP=localhost:9092
DEFAULT_MODEL=yolov11n        # yolov11n | rtdetr-l
VIDEO_SOURCE=data/sample.mp4
TARGET_FPS=5
API_HOST=0.0.0.0
API_PORT=8000
DELTA_PATH=data/detections
```

---

## Project Structure

```
PixelStream/
├── CLAUDE.md                          # Architecture spec / context harness
├── .env.template                      # Config template (copy to .env)
├── pyproject.toml                     # Python deps (uv)
├── docker-compose.yml                 # Optional: Redpanda instead of Kafka
│
├── src/pixelstream/
│   ├── config.py                      # Pydantic settings
│   ├── schemas.py                     # Shared Pydantic models
│   ├── producer/frame_producer.py     # Video → JPEG → Kafka ps.frames
│   ├── processing/
│   │   ├── stream_processor.py        # Spark readStream setup
│   │   └── batch_handler.py          # foreachBatch: decode → infer → write
│   ├── inference/
│   │   ├── base.py                    # InferenceBackend ABC
│   │   ├── mock.py                    # Fake bboxes for unit tests
│   │   └── ultralytics_backend.py     # YOLOv11n + RT-DETR ONNX Runtime
│   ├── storage/delta_writer.py        # Write DetectionResult → Delta Lake
│   └── dashboard/
│       ├── api.py                     # FastAPI: REST + WebSocket
│       └── broadcaster.py             # asyncio.Queue → all WS clients
│
├── dashboard/src/
│   ├── App.tsx
│   ├── components/
│   │   ├── VideoPlayer.tsx            # Video + canvas bbox overlay + detect controls
│   │   ├── LatencyChart.tsx           # Visx line chart (inference_latency_ms)
│   │   ├── ClassBarChart.tsx          # Visx bar chart (detections by class)
│   │   ├── DetectionFeed.tsx          # Scrolling detection log
│   │   ├── ModelSwitch.tsx            # YOLOv11n ↔ RT-DETR toggle
│   │   └── StatusBar.tsx              # FPS / uptime / WS connection state
│   ├── hooks/
│   │   ├── useDetections.ts           # WebSocket + rolling history + pushResult
│   │   └── useStats.ts                # Polls /api/stats every 2 s
│   └── types.ts
│
├── tests/                             # pytest unit + integration tests
└── scripts/
    ├── download_video.sh              # Fetch sample footage
    ├── export_onnx.py                 # One-time ONNX export (needs torch)
    └── run_demo.sh                    # Start all services
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stats` | `{total_frames, total_detections, fps, active_model, uptime_seconds}` |
| `POST` | `/api/detect` | Upload a JPEG frame → `{model, latency_ms, detections[]}` |
| `POST` | `/api/model` | `{"model": "yolov11n" \| "rtdetr-l"}` — hot-swap inference model |
| `GET` | `/api/video/sample` | Serve `data/sample.mp4` with range-request support |
| `GET` | `/api/video/city` | Serve `data/city_traffic.mp4` |
| `GET` | `/api/video/highway` | Serve `data/highway.mp4` |
| `WS` | `/ws/detections` | Stream `DetectionResult` JSON — one message per detected batch |

---

## Tests

```bash
uv run pytest tests/ -v                        # all unit tests (mock backend)
uv run pytest tests/ -m "not integration" -v   # skip Kafka-dependent tests
uv run pytest tests/ -m integration -v         # needs Kafka running
uv run ruff check src/                         # lint
uv run ruff format src/                        # format
```

---

## Extending

**Add a new model**: implement `InferenceBackend.detect()` in `src/pixelstream/inference/`, register the name in `UltralyticsBackend._MODELS` or create a separate backend, then add it to the API model validation set in `api.py`.

**Add a new video source**: add a `GET /api/video/{name}` endpoint in `api.py` and a corresponding preset entry in `dashboard/src/components/VideoPlayer.tsx`.

**Scale out**: replace `local[*]` Spark with a real cluster, point `KAFKA_BOOTSTRAP` at your broker, deploy FastAPI behind a load balancer. The pipeline logic is unchanged.

---

## License

MIT — see [LICENSE](LICENSE).

Models (YOLOv11n, RT-DETR-l) are distributed under the [Ultralytics AGPL-3.0 license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) for open-source use. For commercial use of the models, a separate Ultralytics Enterprise license is required.
