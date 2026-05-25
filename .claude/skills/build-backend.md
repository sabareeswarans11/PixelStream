---
name: build-backend
description: Builds the PixelStream Python backend in strict order. Use when scaffolding or extending the producer, Spark consumer, inference backends, Delta writer, or FastAPI dashboard API. Always follows the build order in CLAUDE.md and implements mock backend before real inference.
---

# Build Backend — PixelStream

You are building the Python backend for PixelStream: a real-time CV streaming pipeline on
Intel Mac (CPU-only, no GPU). Follow the build order exactly.

## Hard Constraints (READ FIRST)
- Device is always `cpu` — never `mps` or `cuda`
- Use `confluent_kafka` only — not `kafka-python` or `pykafka`
- Use `uv` for all package operations
- Use `pydantic` v2 — `.model_dump()` not `.dict()`
- No `print()` — use `structlog.get_logger()`
- All type hints on every function signature

## Build Order (follow strictly, do not skip)

### Step 1 — Scaffold
```bash
uv init pixelstream --python 3.11
# Then write pyproject.toml with full deps from CLAUDE.md
uv sync
```
Verify: `uv run python -c "import pyspark; import confluent_kafka; import ultralytics"`

### Step 2 — Config + Schemas (`src/pixelstream/config.py`, `schemas.py`)
```python
# config.py — Pydantic Settings from .env
class Settings(BaseSettings):
    kafka_bootstrap: str = "localhost:19092"
    default_model: str = "yolov11n"
    inference_device: str = "cpu"
    video_source: str = "data/sample.mp4"
    target_fps: int = 5
    delta_path: str = "data/detections"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

# schemas.py — message contracts
class FrameMessage(BaseModel):
    frame_id: str
    timestamp: float
    source_id: str
    frame_b64: str       # JPEG base64
    width: int
    height: int

class Detection(BaseModel):
    cls: str
    confidence: float
    bbox: list[float]    # [x1, y1, x2, y2] normalized 0-1

class DetectionResult(BaseModel):
    frame_id: str
    timestamp: float
    model: str
    latency_ms: float
    detections: list[Detection]
```
Verify: `uv run python -c "from pixelstream.schemas import FrameMessage"`

### Step 3 — Inference Backends (`src/pixelstream/inference/`)
Always implement `mock.py` FIRST and verify it works before writing `ultralytics_backend.py`.

```python
# base.py
class InferenceBackend(ABC):
    @abstractmethod
    def detect(self, frame_bytes: bytes) -> list[Detection]: ...
    def switch_model(self, model_name: str) -> None:
        raise NotImplementedError

# mock.py — returns 2-3 random boxes, zero latency
class MockBackend(InferenceBackend):
    def detect(self, frame_bytes: bytes) -> list[Detection]:
        return [Detection(cls="person", confidence=0.91, bbox=[0.1, 0.1, 0.4, 0.6])]

# ultralytics_backend.py — real models, lazy load
class UltralyticsBackend(InferenceBackend):
    MODELS = {"yolov11n": "yolo11n.pt", "rtdetr-l": "rtdetr-l.pt"}

    def __init__(self, model_name: str = "yolov11n"):
        self._model_name = model_name
        self._model = None  # lazy

    def _load(self) -> None:
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self.MODELS[self._model_name])

    def detect(self, frame_bytes: bytes) -> list[Detection]:
        self._load()
        img = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
        results = self._model(frame, verbose=False, device="cpu")
        return self._parse(results[0])

    def switch_model(self, model_name: str) -> None:
        self._model = None
        self._model_name = model_name
```
Verify: `uv run pytest tests/test_inference.py -v`

### Step 4 — Frame Producer (`src/pixelstream/producer/frame_producer.py`)
```python
class FrameProducer:
    def __init__(self, source: str, topic: str = "ps.frames",
                 target_fps: int = 5, loop: bool = True):
        self._source = source
        self._producer = Producer({"bootstrap.servers": settings.kafka_bootstrap})

    def start(self) -> None:
        cap = cv2.VideoCapture(self._source)
        frame_delay = 1.0 / self._target_fps
        while True:
            ret, frame = cap.read()
            if not ret:
                if self._loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            frame = cv2.resize(frame, (640, 480))
            _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            msg = FrameMessage(
                frame_id=str(uuid.uuid4()),
                timestamp=time.time(),
                source_id=self._source,
                frame_b64=base64.b64encode(jpg.tobytes()).decode(),
                width=640, height=480
            )
            self._producer.produce("ps.frames", value=msg.model_dump_json().encode())
            self._producer.poll(0)
            time.sleep(frame_delay)
```
Verify: Start Redpanda, run producer for 5s, check `ps.frames` in Redpanda Console.

### Step 5 — Spark Consumer + Delta Writer
See `src/pixelstream/processing/stream_processor.py` and `batch_handler.py`.
Use `MockBackend` first. Verify Delta files appear in `data/detections/`.

### Step 6 — Dashboard API (`src/pixelstream/dashboard/api.py`)
```
GET  /api/stats          → stats JSON
GET  /api/history        → recent detections from Delta
POST /api/model          → hot-swap inference model
WS   /ws/detections      → stream DetectionResult messages
```
Verify: `uv run pixelstream-api &` then `curl localhost:8000/api/stats`

## Verification at each step
```bash
uv run pytest tests/ -m "not integration" -v   # after each module
docker-compose ps                               # Redpanda must be running for integration tests
uv run ruff check src/                         # lint
```

## When You're Done
Run `scripts/run_demo.sh` to verify the full pipeline end-to-end.
Then invoke `/qa-pipeline` to run the QA engineer checks.
