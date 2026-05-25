---
name: download-models
description: Downloads YOLOv11n and RT-DETR-l models locally via ultralytics. Use before running real inference for the first time. Verifies CPU inference works and benchmarks throughput on this machine.
---

# Download Models — PixelStream

Pre-downloads ultralytics models and verifies CPU inference on this machine
(Intel Mac 2019, CPU-only — AMD Radeon not supported by PyTorch).

## What this does
1. Downloads `yolo11n.pt` (~5MB) to `~/.cache/ultralytics/`
2. Downloads `rtdetr-l.pt` (~69MB) to `~/.cache/ultralytics/`
3. Runs a warm-up inference pass on a test frame
4. Reports actual FPS throughput on this CPU
5. Saves a sample detection result to verify output schema

## Steps

### 1. Verify ultralytics is installed
```bash
uv run python -c "from ultralytics import YOLO; print('OK')"
```
If it fails: `uv sync` to reinstall deps.

### 2. Download YOLOv11n and warm up
```python
# Run this via: uv run python scripts/download_models.py
from ultralytics import YOLO
import time, cv2, numpy as np

def benchmark(model_name: str, model_path: str, n_frames: int = 10):
    model = YOLO(model_path)  # triggers download if not cached
    # Create a synthetic 640x480 frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # Warm up
    model(frame, verbose=False, device="cpu")
    # Benchmark
    t0 = time.perf_counter()
    for _ in range(n_frames):
        model(frame, verbose=False, device="cpu")
    elapsed = time.perf_counter() - t0
    fps = n_frames / elapsed
    print(f"{model_name}: {fps:.1f} FPS on CPU ({elapsed/n_frames*1000:.0f}ms/frame)")

benchmark("YOLOv11n", "yolo11n.pt")
benchmark("RT-DETR-l", "rtdetr-l.pt", n_frames=5)  # fewer — it's slower
```

### 3. Expected output (Intel Mac 2019 i7)
```
YOLOv11n:   ~12-18 FPS on CPU  (~60-80ms/frame)
RT-DETR-l:  ~2-4 FPS on CPU   (~250-500ms/frame)
```
RT-DETR-l is substantially slower on CPU — the dashboard model toggle should warn the user.

### 4. Verify detection output schema
```python
from ultralytics import YOLO
import cv2, numpy as np

model = YOLO("yolo11n.pt")
frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
results = model(frame, verbose=False, device="cpu")[0]
for box in results.boxes:
    cls = results.names[int(box.cls)]
    conf = float(box.conf)
    xyxy = box.xyxy[0].tolist()   # [x1, y1, x2, y2] in pixels
    # Normalize to 0-1
    x1, y1, x2, y2 = xyxy[0]/640, xyxy[1]/480, xyxy[2]/640, xyxy[3]/480
    print(f"  {cls}: {conf:.2f} [{x1:.2f},{y1:.2f},{x2:.2f},{y2:.2f}]")
```

### 5. Create `scripts/download_models.py` with the above
Then add to `scripts/run_demo.sh`:
```bash
echo "→ Downloading/verifying models..."
uv run python scripts/download_models.py
```

## Cache location
Models cache at `~/.cache/ultralytics/` — not inside the repo.
Never commit `.pt` files. They're already in `.gitignore`.

## If download fails
- Check internet connection
- Ultralytics downloads from GitHub Releases — no API key needed
- Manual URL: `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`
  and `https://github.com/ultralytics/assets/releases/download/v8.3.0/rtdetr-l.pt`

## After completion
Run `/qa-pipeline` to verify the `UltralyticsBackend` integration tests pass.
