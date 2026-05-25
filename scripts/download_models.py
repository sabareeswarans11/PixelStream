#!/usr/bin/env python3
"""
Pre-downloads YOLOv11n and RT-DETR-l and benchmarks CPU throughput.
Run: uv run python scripts/download_models.py
"""
import time

import cv2
import numpy as np


def benchmark(model_name: str, model_file: str, n_frames: int = 5) -> None:
    from ultralytics import YOLO

    print(f"\n→ Loading {model_name} ({model_file})...")
    model = YOLO(model_file)  # triggers download if not cached

    frame = np.random.randint(0, 200, (480, 640, 3), dtype=np.uint8)

    # warm-up pass
    model(frame, verbose=False, device="cpu")

    print(f"  Benchmarking {n_frames} frames on CPU...")
    t0 = time.perf_counter()
    for _ in range(n_frames):
        model(frame, verbose=False, device="cpu")
    elapsed = time.perf_counter() - t0

    fps = n_frames / elapsed
    ms_per_frame = elapsed / n_frames * 1000
    print(f"  ✓ {model_name}: {fps:.1f} FPS  ({ms_per_frame:.0f} ms/frame)")


if __name__ == "__main__":
    print("PixelStream — Model Download & CPU Benchmark")
    print("Machine: Intel Mac (CPU-only, AMD Radeon not supported by PyTorch)")
    benchmark("YOLOv11n", "yolo11n.pt", n_frames=10)
    benchmark("RT-DETR-l", "rtdetr-l.pt", n_frames=5)
    print("\n✓ Models ready in ~/.cache/ultralytics/")
