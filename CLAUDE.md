# CLAUDE.md — PixelStream

## Project Overview
PixelStream is an open-source real-time streaming computer vision reference pipeline:
video file → Redpanda (Kafka) → Spark Structured Streaming → YOLOv11n / RT-DETR-l inference
(CPU) → Delta Lake → FastAPI WebSocket → React + Visx live dashboard.

**Goal:** One working demo (single video file, local CPU inference, switchable models) that
proves the full architecture end-to-end. No cloud dependencies, no GPU required.

## Machine Constraints (DO NOT IGNORE)
- **Platform**: Intel Mac 2019, macOS
- **GPU**: AMD Radeon 4GB — PyTorch does NOT support AMD on Intel Mac. All inference is CPU-only.
- **PyTorch device**: `"cpu"` always. Never set `device="mps"` or `device="cuda"`.
- **Target throughput**: 2–5 FPS through the full pipeline (Kafka → Spark → inference → dashboard).
  This is acceptable for demo. The architecture scales; the hardware does not.

## Tech Stack
| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Ultralytics requires ≥3.8; structlog/pydantic best on 3.11 |
| Package manager | uv | Lock file, fast install, virtual env management |
| Message bus | Redpanda (Docker) | Single binary, Kafka-compatible, zero ZooKeeper |
| Stream processing | PySpark 3.5.x (local mode) | `local[*]` — no cluster needed for demo |
| Inference | Ultralytics (YOLOv11n + RT-DETR-l) | Both open-source MIT, same API, CPU-runnable |
| Storage | Delta Lake | Structured detection history; queryable offline |
| API | FastAPI + Uvicorn | WebSocket + REST in one process |
| Dashboard | React 18 + Vite + Tailwind + Visx | Airbnb's D3 wrapper; bbox overlay on canvas |
| Kafka client | confluent-kafka | Only maintained Python Kafka client |
| Config | Pydantic v2 + pydantic-settings | Typed settings from env |
| Logging | structlog | Structured JSON logs |
| Testing | pytest | Unit (mock) + integration (Redpanda) |

## Models (Open-Source, MIT License)
Both models ship via the `ultralytics` Python package. No separate download needed — they
auto-download to `~/.cache/ultralytics/` on first use.

```
YOLOv11n   yolo11n.pt    ~5 MB   ~15 FPS CPU   nano, fastest, good enough for demo
RT-DETR-l  rtdetr-l.pt   ~69 MB  ~2-3 FPS CPU  larger, more accurate on small objects
```

- `from ultralytics import YOLO` — same class for both models
- `model = YOLO("yolo11n.pt")` or `model = YOLO("rtdetr-l.pt")`
- `results = model(frame_bgr, verbose=False)` — synchronous, returns list[Results]
- Both are pretrained on COCO (80 classes). No fine-tuning needed for demo.
- **Default model on startup**: YOLOv11n (faster on CPU). RT-DETR switchable via dashboard toggle.

## Architecture
```
┌──────────────┐     ┌─────────────┐     ┌───────────────────────────┐     ┌────────────┐
│ Video File   │────▶│  Redpanda   │────▶│  Spark Structured         │────▶│ Delta Lake │
│ (sample.mp4) │     │  topic:     │     │  Streaming (local[*])     │     │ /data/     │
│ looped       │     │  ps.frames  │     │                           │     │ detections/│
└──────────────┘     │             │     │  foreachBatch:            │     └────────────┘
      ▲              │  topic:     │     │  1. decode JPEG bytes     │
      │              │  ps.detect  │◀────│  2. run YOLO/RT-DETR      │
FrameProducer        └─────────────┘     │  3. write → Delta Lake    │
(Python process)                         │  4. publish → ps.detect   │
                                         └───────────────────────────┘
                                                        │
                                              FastAPI WebSocket
                                                        │
                                              ┌─────────────────┐
                                              │ React Dashboard  │
                                              │ - Live bbox view │
                                              │ - Visx charts    │
                                              │ - Model toggle   │
                                              └─────────────────┘
```

## Directory Structure
```
pixelstream/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── docker-compose.yml            # Redpanda only (no ZooKeeper)
├── .env.template
├── .env                          # gitignored, copied from template
├── .gitignore
├── data/
│   ├── sample.mp4                # downloaded by scripts/download_video.sh
│   └── detections/               # Delta Lake output (auto-created)
├── src/pixelstream/
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings — all config from env
│   ├── schemas.py                # Pydantic models: FrameMessage, Detection, DetectionResult
│   ├── producer/
│   │   ├── __init__.py
│   │   └── frame_producer.py     # Read video file in loop → JPEG → Kafka ps.frames
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── stream_processor.py   # Spark readStream → foreachBatch → start()
│   │   └── batch_handler.py      # Deserialize → infer → Delta + Kafka
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── base.py               # ABC: detect(frame_bytes) → list[Detection]
│   │   ├── mock.py               # Returns fake bboxes — for unit tests only
│   │   └── ultralytics_backend.py # YOLOv11n + RT-DETR-l, switchable at runtime
│   ├── storage/
│   │   ├── __init__.py
│   │   └── delta_writer.py       # Write DetectionResult to Delta Lake
│   └── dashboard/
│       ├── __init__.py
│       ├── api.py                # FastAPI: WS /ws/detections, GET /api/stats, POST /api/model
│       └── broadcaster.py        # Async queue → broadcast to all WS clients
├── dashboard/                    # React source (separate from Python)
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── LiveFeed.jsx       # Canvas with bbox overlay from WS stream
│       │   ├── DetectionChart.jsx # Visx AreaStack: detections/sec over time
│       │   ├── StatsPanel.jsx     # FPS, latency, detection count, active model
│       │   └── ModelSelector.jsx  # Toggle: YOLOv11n ↔ RT-DETR-l
│       └── hooks/
│           └── useWebSocket.js   # Auto-reconnect WebSocket hook
├── tests/
│   ├── conftest.py               # SparkSession fixture, mock backend fixture
│   ├── test_producer.py
│   ├── test_inference.py         # Tests mock + ultralytics with a real frame
│   ├── test_processor.py
│   └── fixtures/
│       └── sample_frame.jpg      # Single frame for inference tests
├── scripts/
│   ├── download_video.sh         # wget public domain traffic clip → data/sample.mp4
│   └── run_demo.sh               # docker-compose up -d → producer → spark → dashboard
└── monitoring/
    └── prometheus.yml
```

## Kafka Topics
| Topic | Producer | Consumer | Message format |
|---|---|---|---|
| `ps.frames` | FrameProducer | Spark | JSON: `{frame_id, timestamp, source_id, frame_b64, width, height}` |
| `ps.detections` | Spark batch_handler | FastAPI broadcaster | JSON: `{frame_id, timestamp, model, latency_ms, detections: [{class, conf, bbox}]}` |

- Kafka key: `frame_id` (UUID string)
- Frame encoding: JPEG quality=80 → base64. Target size <50KB per frame.
- Spark reads `ps.frames`, writes to `ps.detections`. Dashboard reads `ps.detections`.

## Inference Backend
```python
# src/pixelstream/inference/ultralytics_backend.py

class UltralyticsBackend(InferenceBackend):
    MODELS = {
        "yolov11n": "yolo11n.pt",
        "rtdetr-l": "rtdetr-l.pt",
    }

    def __init__(self, model_name: str = "yolov11n"):
        self._model_name = model_name
        self._model: YOLO | None = None  # lazy load

    def _load(self):
        if self._model is None:
            self._model = YOLO(self.MODELS[self._model_name])

    def detect(self, frame_bytes: bytes) -> list[Detection]:
        self._load()
        img = decode_jpeg(frame_bytes)           # → numpy HWC BGR
        results = self._model(img, verbose=False)
        return _parse_results(results)

    def switch_model(self, model_name: str) -> None:
        """Hot-swap model. Called from FastAPI POST /api/model."""
        self._model = None
        self._model_name = model_name
```
- Lazy load: model loads on first `detect()` call, not at import time.
- `switch_model()` sets `_model = None` → next call reloads. Thread-safe enough for demo.
- `decode_jpeg`: `np.frombuffer(frame_bytes, np.uint8)` → `cv2.imdecode(..., cv2.IMREAD_COLOR)`

## Spark Integration
```python
# src/pixelstream/processing/stream_processor.py
spark = (SparkSession.builder
    .appName("PixelStream")
    .master("local[*]")
    .config("spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "io.delta:delta-spark_2.12:3.2.0")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.sql.shuffle.partitions", "2")   # low for local dev
    .getOrCreate())
```
- `foreachBatch` receives a Spark DataFrame. Collect to Python list, call inference, write results.
- Spark Jars download on first run (~200MB). Cache in `~/.ivy2/`.
- Keep micro-batch interval at 5s (`trigger(processingTime="5 seconds")`).

## Dashboard API (FastAPI)
```
GET  /                     → serve React build (static)
GET  /api/stats            → {total_frames, total_detections, fps, active_model, uptime}
GET  /api/history?minutes=5 → list[DetectionResult] from Delta Lake
POST /api/model            → {"model": "yolov11n" | "rtdetr-l"} — hot-swap
WS   /ws/detections        → streams DetectionResult JSON as text frames
```
- FastAPI app reads `ps.detections` Kafka topic in a background asyncio task.
- Each message is parsed and pushed into an `asyncio.Queue`.
- Broadcaster pulls from queue, sends to all connected WebSocket clients.
- React polls `/api/stats` every 2s for the stats panel.
- React streams `/ws/detections` for live feed + charts.

## React Dashboard
- **LiveFeed.jsx**: canvas element sized to 320×240. On each WS message, draw thumbnail
  (if included) then overlay bboxes as colored rectangles. Class label above each box.
- **DetectionChart.jsx**: Visx AreaStack. X = time (last 60s), Y = detection count per class.
  Rolling window of 60 data points, one per second.
- **StatsPanel.jsx**: FPS / latency / model name / total count. Updates every 2s from REST.
- **ModelSelector.jsx**: Two buttons (YOLOv11n / RT-DETR-l). POST /api/model on click.
  Disabled while switching (500ms debounce).

## Frame Producer
```python
class FrameProducer:
    def __init__(self, source: str, topic: str = "ps.frames",
                 target_fps: int = 5, loop: bool = True):
        ...
    def start(self) -> None:
        """Blocking. Reads video, publishes at target_fps, loops when EOF."""
```
- `source`: path to `data/sample.mp4`
- Resize frames to 640×480 before JPEG encoding (keeps Kafka messages small).
- Publish at 5 FPS max. Use `time.sleep()` between frames to pace.
- Loop: when video ends, `cap.set(cv2.CAP_PROP_POS_FRAMES, 0)` to restart.

## Docker Compose (Redpanda only)
```yaml
services:
  redpanda:
    image: redpandadata/redpanda:v23.3.21
    command:
      - redpanda
      - start
      - --smp 1
      - --memory 512M
      - --reserve-memory 0M
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092,OUTSIDE://0.0.0.0:19092
      - --advertise-kafka-addr PLAINTEXT://redpanda:9092,OUTSIDE://localhost:19092
    ports:
      - "19092:19092"   # external (use this from host)
      - "9644:9644"     # admin

  redpanda-console:
    image: docker.redpanda.com/redpandadata/console:v2.4.3
    environment:
      CONFIG_FILEPATH: /tmp/config.yml
    volumes:
      - ./monitoring/redpanda-console.yml:/tmp/config.yml
    ports:
      - "8080:8080"     # Web UI for inspecting topics
    depends_on:
      - redpanda
```
- Host connects on `localhost:19092`. Code in containers uses `redpanda:9092`.
- Redpanda Console at `http://localhost:8080` — inspect topics, messages, consumer groups.
- No PostgreSQL in base stack. Delta Lake handles all detection storage.

## Environment Variables (.env)
```
# Kafka
KAFKA_BOOTSTRAP=localhost:19092

# Spark
SPARK_LOCAL_DIR=/tmp/spark-local

# Inference
DEFAULT_MODEL=yolov11n          # yolov11n | rtdetr-l
INFERENCE_DEVICE=cpu            # always cpu on Intel Mac

# Producer
VIDEO_SOURCE=data/sample.mp4
TARGET_FPS=5

# Dashboard API
API_HOST=0.0.0.0
API_PORT=8000

# Delta Lake
DELTA_PATH=data/detections
```

## pyproject.toml Dependencies
```toml
[project]
name = "pixelstream"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyspark>=3.5.0,<4.0",
    "delta-spark>=3.2.0",
    "confluent-kafka>=2.6.0",
    "ultralytics>=8.3.0",         # YOLOv11 + RT-DETR, MIT license
    "opencv-python-headless>=4.10.0",
    "numpy>=1.26.0,<2.0",         # ultralytics pins <2.0
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=14.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "python-dotenv>=1.0.0",
    "pandas>=2.2.0",
    "pyarrow>=18.0.0",
    "Pillow>=11.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[project.scripts]
pixelstream-producer = "pixelstream.producer.frame_producer:main"
pixelstream-spark    = "pixelstream.processing.stream_processor:main"
pixelstream-api      = "pixelstream.dashboard.api:main"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["integration: requires Redpanda running"]
```

## Build Order (follow strictly)
1. **Scaffold**: `pyproject.toml`, `CLAUDE.md`, `.env.template`, `.gitignore`
2. **Docker Compose**: Redpanda + Console. Verify `docker-compose up -d` works.
3. **Config + Schemas**: `config.py` (Pydantic Settings) + `schemas.py` (FrameMessage, Detection, DetectionResult)
4. **Inference Backends**: `base.py` → `mock.py` → `ultralytics_backend.py`
5. **Frame Producer**: `frame_producer.py`. Test: publish 10 frames, verify in Redpanda Console.
6. **Spark Consumer**: `stream_processor.py` + `batch_handler.py`. Test with mock backend.
7. **Delta Writer**: `delta_writer.py`. Verify Parquet files appear in `data/detections/`.
8. **Dashboard API**: `api.py` + `broadcaster.py`. Test WebSocket with `wscat`.
9. **React Dashboard**: Components in order: StatsPanel → ModelSelector → DetectionChart → LiveFeed.
10. **Integration**: Wire everything together. Run `scripts/run_demo.sh`.
11. **Sample Video**: `scripts/download_video.sh` — download public domain clip.
12. **Tests**: Fill in `tests/` for each module.

## Coding Conventions
- All imports: absolute (`from pixelstream.inference.base import InferenceBackend`)
- Type hints on ALL function signatures — no bare `dict`, use `dict[str, Any]`
- Pydantic v2 models for all message schemas (use `model_dump()` not `.dict()`)
- `structlog.get_logger()` for all logging — never `print()` in production code
- `confluent_kafka.Producer` / `Consumer` — not pykafka, not kafka-python
- JPEG quality=80 for Kafka transport (balance size vs quality)
- Frame resize to 640×480 before encoding (producer side)
- All secrets from env — never hardcoded
- `asyncio.run()` inside Spark foreachBatch if calling async code

## DO NOT
- Set `device="mps"` or `device="cuda"` — Intel Mac AMD GPU is not supported by PyTorch
- Install `torch` separately — `ultralytics` brings the right version as a dependency
- Use `kafka-python` or `pykafka` — unmaintained, use `confluent-kafka`
- Use `cv2.imshow()` — headless only (`opencv-python-headless`)
- Send full-resolution frames over WebSocket to browser — send 320px thumbnails + bbox metadata
- Make Spark UDFs async — call `asyncio.run()` inside synchronous UDF if needed
- Overengineer the dashboard — demo quality is the goal, not production SLA
- Start with real models — always implement mock backend first and verify pipeline, then swap in real

## Running the Demo
```bash
# 1. Start Redpanda
docker-compose up -d

# 2. Install Python deps
uv sync

# 3. Download sample video
bash scripts/download_video.sh

# 4. Start Spark consumer (terminal 1)
uv run pixelstream-spark

# 5. Start frame producer (terminal 2)
uv run pixelstream-producer

# 6. Start FastAPI dashboard backend (terminal 3)
uv run pixelstream-api

# 7. Start React dev server (terminal 4)
cd dashboard && npm run dev

# Open http://localhost:5173 — live dashboard
# Open http://localhost:8080 — Redpanda Console (topic inspector)
```

## Testing
```bash
uv run pytest tests/ -v                          # all unit tests (mock backend)
uv run pytest tests/ -m "not integration" -v    # skip Kafka-dependent tests
uv run pytest tests/ -m integration -v          # needs docker-compose up -d
uv run ruff check src/                           # lint
uv run ruff format src/                         # format
```
