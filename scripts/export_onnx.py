#!/usr/bin/env python3
"""
Export YOLOv11n and RT-DETR-l to ONNX for CPU inference via ONNX Runtime.

Run inside the pixelstream-export conda env:
    conda run -n pixelstream-export python scripts/export_onnx.py
"""

import pathlib
import shutil
import sys

MODELS = {
    "yolov11n": "yolo11n.pt",
    "rtdetr-l": "rtdetr-l.pt",
}
ONNX_DIR = pathlib.Path("data/models")


def export(name: str, pt_file: str) -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    out = ONNX_DIR / f"{name}.onnx"
    if out.exists():
        print(f"  ✓ {out} already exists — skipping")
        return

    print(f"\n→ Exporting {name} ({pt_file}) → {out}")
    ONNX_DIR.mkdir(parents=True, exist_ok=True)

    model = YOLO(pt_file)
    model.export(format="onnx", imgsz=640, simplify=True, opset=17)

    # ultralytics writes the .onnx next to the .pt; move it to data/models/
    candidate = pathlib.Path(pt_file).with_suffix(".onnx")
    if not candidate.exists():
        # try the Ultralytics cache location
        import ultralytics  # noqa: PLC0415

        cache = pathlib.Path(ultralytics.__file__).parent.parent / "runs" / "export"
        candidates = list(cache.rglob(f"{name}.onnx"))
        if candidates:
            candidate = max(candidates, key=lambda p: p.stat().st_mtime)

    if candidate.exists():
        shutil.move(str(candidate), str(out))
        print(f"  ✓ Saved: {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"  ✗ Export produced no file — expected near {candidate}", file=sys.stderr)
        sys.exit(1)


def verify(name: str) -> None:
    import numpy as np  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415

    path = ONNX_DIR / f"{name}.onnx"
    print(f"\n→ Verifying {path} with ONNX Runtime…")
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    dummy = np.random.rand(1, 3, 640, 640).astype("float32")
    out = sess.run(None, {inp.name: dummy})
    print(f"  ✓ Output shape: {out[0].shape}")


if __name__ == "__main__":
    print("PixelStream — ONNX Export")
    print("Exporting to:", ONNX_DIR.resolve())

    for name, pt in MODELS.items():
        export(name, pt)

    # Verify with onnxruntime if available
    try:
        import onnxruntime  # noqa: F401

        for name in MODELS:
            verify(name)
    except ImportError:
        print("\nonnxruntime not in this env — skipping verification (will run fine in uv env)")

    print("\n✓ All models exported. Run the pipeline with: bash scripts/run_demo.sh")
