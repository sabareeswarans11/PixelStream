# CLAUDE.md — PixelStream

## Project Overview
PixelStream is an open-source real-time streaming computer vision reference architecture built on
Spark Structured Streaming + Kafka + GPU inference backends. It ingests live video frames (RTSP,
RTMP, Kafka, or file-based), runs distributed object detection / anomaly detection / classification,
writes results to Delta Lake, and serves a live React dashboard.

**The gap this fills:** Search "Kafka + Spark Structured Streaming + CV inference" — there is NO
clean open-source reference implementation. Everyone describes this architecture in blog posts
but nobody publishes working code. PixelStream is that reference implementation.

## Target User
ML/Data engineers building real-time CV pipelines for surveillance, quality inspection, retail
analytics, or IoT monitoring who need a production-grade streaming architecture, not a Jupyter
notebook with `cv2.VideoCapture()`.

## Tech Stack
- **Language**: Python 3.11
- **Stream Processing**: Spark Structured Streaming (PySpark 3.5.x, local mode for dev)
- **Message Bus**: Redpanda (Kafka-compatible, lighter weight) via Docker
- **Storage**: Delta Lake for detections, PostgreSQL for metadata
- **CV Inference**: Modal serverless GPU (YOLOv11, RT-DETR, Grounding DINO), mock backend for dev
- **Dashboard**: React + Visx (D3-based) + FastAPI WebSocket backend
- **Monitoring**: Prometheus + Grafana in Docker
- **Testing**: pytest
- **Packaging**: pyproject.toml with uv

## Architecture
```
┌──────────────┐     ┌───────────┐     ┌──────────────────────┐     ┌────────────┐
│ Video Source  │────▶│ Redpanda  │────▶│ Spark Structured     │────▶│ Delta Lake │
│ (RTSP/file/  │     │ (Kafka)   │     │ Streaming            │     │ (results)  │
│  webcam)     │     │           │     │                      │     └────────────┘
└──────────────┘     │ topic:    │     │  foreachBatch:       │            │
                     │ frames    │     │  ┌────────────────┐  │            ▼
┌──────────────┐     │           │     │  │ GPU Inference   │  │     ┌────────────┐
│ Frame        │────▶│ topic:    │     │  │ (Modal/mock)    │  │────▶│ Kafka topic│
│ Producer     │     │ detections│◀────│  │ YOLOv11/RT-DETR │  │     │ detections │
│ (Python)     │     └───────────┘     │  └────────────────┘  │     └────────────┘
└──────────────┘                       └──────────────────────┘            │
                                                                          ▼
                                                                   ┌────────────┐
                                                                   │ React+Visx │
                                                                   │ Dashboard  │
                                                                   │ (WebSocket)│
                                                                   └────────────┘
```

## Directory Structure
```
pixelstream/
├── CLAUDE.md                         # This file
├── README.md
├── pyproject.toml
├── docker-compose.yml                # Redpanda + PostgreSQL + Prometheus + Grafana
├── .env.template
├── .gitignore
├── LICENSE                           # MIT
├── src/pixelstream/
│   ├── __init__.py
│   ├── config.py                     # Pydantic settings
│   ├── producer/
│   │   ├── __init__.py
│   │   ├── frame_producer.py         # Read video → publish frames to Kafka
│   │   ├── rtsp_source.py            # RTSP/RTMP stream reader (OpenCV)
│   │   └── file_source.py            # Read from video file or image directory
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── stream_processor.py       # Spark Structured Streaming consumer
│   │   ├── frame_decoder.py          # Decode frame bytes, resize, preprocess
│   │   └── batch_handler.py          # foreachBatch logic: decode → infer → write
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── base.py                   # Abstract inference backend
│   │   ├── mock.py                   # Returns fake bounding boxes (for dev)
│   │   ├── modal_yolo.py             # Modal serverless: YOLOv11 on GPU
│   │   └── api_backend.py            # Generic OpenAI-compatible vision API
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── delta_writer.py           # Write detections to Delta Lake
│   │   └── kafka_publisher.py        # Publish detections back to Kafka
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── api.py                    # FastAPI + WebSocket server
│   │   └── static/                   # React+Visx build output (or dev server)
│   │       └── .gitkeep
│   └── metrics.py                    # Prometheus metrics
├── dashboard/                        # React source (separate from Python)
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx                   # Main dashboard component
│   │   ├── components/
│   │   │   ├── LiveFeed.jsx          # WebSocket frame display with bbox overlay
│   │   │   ├── DetectionChart.jsx    # Visx time-series chart of detections
│   │   │   ├── StatsPanel.jsx        # Live stats: FPS, latency, detection count
│   │   │   └── ModelSelector.jsx     # Switch models on the fly
│   │   └── hooks/
│   │       └── useWebSocket.js       # WebSocket connection hook
│   └── tailwind.config.js
├── tests/
│   ├── conftest.py
│   ├── test_producer.py
│   ├── test_processor.py
│   ├── test_inference.py
│   ├── test_storage.py
│   └── fixtures/
│       ├── sample_frame.jpg
│       └── sample_video.mp4          # 5-second clip for testing
├── scripts/
│   ├── download_sample_video.sh      # Download a public test video
│   └── run_demo.sh                   # Start everything: docker-compose + producer + spark + dashboard
└── tasks/
    ├── 01-scaffold.md
    ├── 02-docker-compose.md
    ├── 03-frame-producer.md
    ├── 04-inference-backends.md
    ├── 05-spark-streaming.md
    ├── 06-delta-writer.md
    ├── 07-dashboard-api.md
    ├── 08-react-dashboard.md
    ├── 09-tests.md
    └── 10-demo.md
```

## Conventions
- All imports use absolute paths: `from pixelstream.producer.frame_producer import FrameProducer`
- Type hints on ALL function signatures
- Docstrings on all public methods (Google style)
- Use `httpx` for any HTTP API calls
- Use `confluent-kafka` Python client for Kafka producer (NOT pykafka or kafka-python — they're dead)
- Use `pydantic` v2 for all config and data models
- Logging via `structlog`
- All API keys from environment variables, NEVER hardcoded
- Frame encoding: JPEG (quality=85) for Kafka transport, PNG for storage
- Kafka messages use Avro or JSON schema with: `{timestamp, source_id, frame_id, frame_bytes_b64, width, height}`
- Detection output schema: `{frame_id, timestamp, detections: [{class, confidence, bbox: [x1,y1,x2,y2]}], model, latency_ms}`

## Key Design Decisions

### 1. Redpanda over Kafka
Redpanda is a single-binary Kafka-compatible broker. For local dev, it starts in <5 seconds in Docker
with zero ZooKeeper/KRaft configuration. Production users can swap in real Kafka with zero code changes
since the API is identical. Docker Compose uses `redpandadata/redpanda:latest`.

### 2. Frame Producer
A standalone Python process that reads video and publishes frames to Kafka:
```python
class FrameProducer:
    def __init__(self, source: str, topic: str = "frames", fps: int = 5):
        ...
    def start(self):
        """Read frames at target FPS, encode as JPEG, publish to Kafka."""
```
Sources: RTSP URL, local video file, directory of images, or webcam (device index).
For the demo, use a public traffic camera RTSP feed or a downloaded sample video.

### 3. Spark Structured Streaming
The consumer reads from Kafka, decodes frames, calls inference, writes results:
```python
spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "frames") \
    .load() \
    .writeStream \
    .foreachBatch(batch_handler) \
    .start()
```
Inside `batch_handler`:
1. Deserialize frame bytes from Kafka value
2. Call inference backend (mock for dev, Modal for GPU)
3. Write detections to Delta Lake table
4. Optionally publish detections to a second Kafka topic for the dashboard

### 4. Inference Backends
All backends implement:
```python
class InferenceBackend(ABC):
    @abstractmethod
    def detect(self, frame_bytes: bytes) -> list[Detection]:
        ...
```
- **MockBackend**: Returns 2-3 random bounding boxes with fake classes. Zero latency.
- **ModalYOLO**: Calls a Modal serverless function decorated with `@app.function(gpu="T4")`.
  The Modal function loads YOLOv11 once (warm container) and runs inference per frame.
- **APIBackend**: Calls any OpenAI-compatible vision API (Together.ai, Gemini) for VLM-based detection.

### 5. Dashboard
React + Visx (Airbnb's D3 wrapper for React). Two data channels:
- **WebSocket**: Live detection stream from FastAPI → React for real-time overlay
- **REST**: Historical aggregates from Delta Lake → Visx charts

Dashboard components:
- Live video feed with bounding box overlay (canvas-based)
- Time-series detection count chart (Visx AreaStack)
- Per-class detection breakdown (Visx BarChart)
- Live stats: FPS, avg latency, total detections, active models
- Model switch toggle (swap backends without restart)

### 6. Local Development (Intel Mac, no GPU)
- Redpanda in Docker: single container, <100MB RAM
- Spark in local mode: `master("local[*]")`
- MockBackend: all tests and dev use fake detections, zero API calls
- Frame producer reads a 5-second sample video in a loop
- Dashboard dev server: `cd dashboard && npm run dev`
- Full stack starts with `docker-compose up -d && python -m pixelstream.producer --source sample.mp4`

## Testing
- `pytest tests/` — all pass with mock backend
- `pytest tests/ -m "not integration"` — no Kafka, no API
- Tests that need Kafka use a pytest fixture that checks if Redpanda is running, skip otherwise
- SparkSession fixture in conftest.py (same pattern as SparkOCR-VLM)

## Dependencies (pyproject.toml)
```
dependencies = [
    "pyspark>=3.5.0,<4.0",
    "delta-spark>=3.2.0",
    "confluent-kafka>=2.6.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "Pillow>=11.0.0",
    "opencv-python-headless>=4.10.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=14.0",
    "prometheus-client>=0.21.0",
    "python-dotenv>=1.0.0",
    "numpy>=1.26.0",
    "pandas>=2.2.0",
    "pyarrow>=18.0.0",
]

[project.optional-dependencies]
modal = ["modal>=0.73.0"]
dev = ["pytest>=8.3.0", "pytest-cov>=6.0.0", "ruff>=0.8.0"]
```

## Do NOT
- Install torch/torchvision locally — inference is via Modal or API, not local GPU
- Use kafka-python or pykafka — they are unmaintained; use confluent-kafka
- Bundle the React build inside the Python package — keep them separate
- Use OpenCV's `imshow` — headless only (`opencv-python-headless`)
- Make Spark UDFs async — synchronous only, use `asyncio.run()` inside if calling async backends
- Over-engineer the dashboard — it's a demo, not a product. Keep it clean and minimal
- Create real-time video streaming through WebSocket — too much bandwidth. Send detection metadata
  + annotated frame thumbnails (320px wide) instead

## Build Order
1. **Docker Compose**: Redpanda + PostgreSQL + Prometheus + Grafana
2. **Config + Schema**: Pydantic models for frames, detections, config
3. **Frame Producer**: Read video file → publish JPEG frames to Redpanda
4. **Inference Backends**: MockBackend first, then ModalYOLO, then APIBackend
5. **Spark Streaming Consumer**: Read from Kafka → foreachBatch → inference → Delta
6. **Delta Writer**: Write detection results to Delta Lake tables
7. **Dashboard API**: FastAPI + WebSocket serving detection stream
8. **React Dashboard**: Visx charts + live detection overlay
9. **Tests**: Unit tests with mock backend, integration tests with Redpanda
10. **Demo script**: `run_demo.sh` that starts everything with one command
11. **README + architecture diagram + demo GIF**

## Docker Compose Services
```yaml
services:
  redpanda:
    image: redpandadata/redpanda:latest
    command:
      - redpanda start
      - --smp 1
      - --memory 512M
      - --reserve-memory 0M
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
    ports:
      - "9092:9092"    # Kafka API
      - "9644:9644"    # Admin API
      - "8082:8082"    # Schema Registry

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: pixelstream
      POSTGRES_USER: pixelstream
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    ports:
      - "3001:3000"
```

## Environment Variables
```
MODAL_TOKEN_ID=...         # For Modal GPU inference
MODAL_TOKEN_SECRET=...
TOGETHER_API_KEY=...       # For API-based VLM detection
GEMINI_API_KEY=...         # For Gemini vision detection
KAFKA_BOOTSTRAP=localhost:9092
POSTGRES_URL=postgresql://pixelstream:dev@localhost:5432/pixelstream
```
