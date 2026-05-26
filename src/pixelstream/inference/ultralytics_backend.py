"""
ONNX Runtime inference backend for PixelStream.

PyTorch has no wheels for Intel Mac x86_64 on macOS 15+. We use ONNX Runtime instead,
which is 2-3x faster on CPU anyway. First use auto-exports each model to ONNX via
ultralytics (which uses torch internally during export — torch must be installed separately
for the one-time export step).

Model files:
  ~/.cache/ultralytics/yolo11n.pt      — ultralytics source (auto-downloaded)
  data/models/yolo11n.onnx             — ONNX export (auto-created on first detect)
  data/models/rtdetr-l.onnx            — ONNX export (auto-created on first detect)
"""

import pathlib
import threading
import time
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
import structlog

from pixelstream.inference.base import InferenceBackend
from pixelstream.schemas import Detection

log = structlog.get_logger()

_MODELS: dict[str, str] = {
    "yolov11n": "yolo11n.pt",
    "rtdetr-l": "rtdetr-l.pt",
}
_ONNX_DIR = pathlib.Path("data/models")
_INPUT_SIZE = (640, 640)  # ultralytics models expect 640×640


class UltralyticsBackend(InferenceBackend):
    """
    Runs YOLOv11n or RT-DETR-l via ONNX Runtime on CPU.
    Models are auto-exported to ONNX on first detect() call.
    Thread-safe: a Lock serializes detect() and switch_model().
    """

    def __init__(self, model_name: str = "yolov11n") -> None:
        if model_name not in _MODELS:
            raise ValueError(f"Unknown model '{model_name}'. Choose from: {list(_MODELS)}")
        self._model_name = model_name
        self._session: ort.InferenceSession | None = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def _onnx_path(self) -> pathlib.Path:
        return _ONNX_DIR / f"{self._model_name}.onnx"

    def _ensure_onnx(self) -> pathlib.Path:
        """Export to ONNX if the file doesn't exist yet."""
        onnx_path = self._onnx_path()
        if onnx_path.exists():
            return onnx_path

        _ONNX_DIR.mkdir(parents=True, exist_ok=True)
        log.info("exporting_onnx", model=self._model_name, dest=str(onnx_path))

        try:
            from ultralytics import YOLO  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("ultralytics not installed. Run: uv sync") from exc

        pt_model = YOLO(_MODELS[self._model_name])
        pt_model.export(format="onnx", imgsz=640, simplify=True, opset=17)

        # ultralytics exports to the same dir as the .pt file; move to our models dir
        default_out = pathlib.Path(_MODELS[self._model_name]).with_suffix(".onnx")
        if not default_out.exists():
            # try the ultralytics cache location
            import ultralytics  # noqa: PLC0415

            cache = pathlib.Path(ultralytics.__file__).parent.parent / "runs" / "export"
            candidates = list(cache.rglob(f"{self._model_name}.onnx"))
            if candidates:
                default_out = candidates[-1]

        if default_out.exists():
            default_out.rename(onnx_path)
        else:
            raise RuntimeError(f"ONNX export produced no file. Expected: {default_out}")

        log.info("onnx_exported", model=self._model_name, path=str(onnx_path))
        return onnx_path

    def _load_session(self) -> None:
        """Load ONNX Runtime session. Must be called under self._lock."""
        if self._session is not None:
            return
        onnx_path = self._ensure_onnx()
        log.info("loading_ort_session", model=self._model_name, path=str(onnx_path))
        self._session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )
        log.info("ort_session_ready", model=self._model_name)

    def detect(self, frame_bytes: bytes) -> list[Detection]:
        with self._lock:
            self._load_session()
            assert self._session is not None

            img_array = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is None:
                log.warning("frame_decode_failed")
                return []

            orig_h, orig_w = frame.shape[:2]
            blob = self._preprocess(frame)

            t0 = time.perf_counter()
            input_name = self._session.get_inputs()[0].name
            outputs = self._session.run(None, {input_name: blob})
            latency_ms = (time.perf_counter() - t0) * 1000
            log.debug("ort_inference", model=self._model_name, latency_ms=round(latency_ms, 1))

            return self._postprocess(outputs, orig_w, orig_h)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """BGR frame → float32 NCHW blob normalized to [0, 1]."""
        resized = cv2.resize(frame, _INPUT_SIZE)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        return np.expand_dims(blob.transpose(2, 0, 1), axis=0)  # NCHW

    def _postprocess(
        self, outputs: list[Any], orig_w: int, orig_h: int, conf_thresh: float = 0.25
    ) -> list[Detection]:
        """
        Parse ONNX output into Detection objects.

        YOLO: output [1, 4+num_classes, num_anchors] — transposed format, pixel-space xywh.
        RT-DETR: output [1, num_queries, 6] where 6 = [x1,y1,x2,y2,conf,class_id], normalized.
        """
        detections: list[Detection] = []
        raw = outputs[0]

        if raw.ndim == 3:
            raw = raw[0]  # squeeze batch dim

        names = self._get_class_names()

        # RT-DETR: [num_queries, 6] — coords are already normalized xyxy, not xywh
        if raw.shape[-1] == 6:
            confidences = raw[:, 4]
            keep = confidences >= conf_thresh
            raw = raw[keep]
            for row in raw:
                x1, y1, x2, y2 = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                conf = float(row[4])
                cid = int(row[5])
                detections.append(
                    Detection(
                        cls=names.get(cid, str(cid)),
                        confidence=round(conf, 4),
                        bbox=[
                            round(max(0.0, x1), 4),
                            round(max(0.0, y1), 4),
                            round(min(1.0, x2), 4),
                            round(min(1.0, y2), 4),
                        ],
                    )
                )
            return detections

        # YOLO: [4+num_classes, num_anchors] → transpose to [num_anchors, 4+num_classes]
        if raw.shape[0] < raw.shape[-1]:
            raw = raw.T

        boxes_xywh = raw[:, :4]  # cx, cy, w, h in 640px space
        scores = raw[:, 4:]      # [num_boxes, num_classes]
        class_ids = np.argmax(scores, axis=1)
        confidences = scores[np.arange(len(scores)), class_ids]

        keep = confidences >= conf_thresh
        boxes_xywh = boxes_xywh[keep]
        confidences = confidences[keep]
        class_ids = class_ids[keep]

        for (cx, cy, w, h), conf, cid in zip(boxes_xywh, confidences, class_ids):
            x1 = (cx - w / 2) / _INPUT_SIZE[0]
            y1 = (cy - h / 2) / _INPUT_SIZE[1]
            x2 = (cx + w / 2) / _INPUT_SIZE[0]
            y2 = (cy + h / 2) / _INPUT_SIZE[1]
            detections.append(
                Detection(
                    cls=names.get(int(cid), str(cid)),
                    confidence=round(float(conf), 4),
                    bbox=[
                        round(max(0.0, x1), 4),
                        round(max(0.0, y1), 4),
                        round(min(1.0, x2), 4),
                        round(min(1.0, y2), 4),
                    ],
                )
            )
        return detections

    def _get_class_names(self) -> dict[int, str]:
        # COCO class names (80 classes) — hardcoded as fallback
        return {
            0: "person",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            4: "airplane",
            5: "bus",
            6: "train",
            7: "truck",
            8: "boat",
            9: "traffic light",
            10: "fire hydrant",
            11: "stop sign",
            12: "parking meter",
            13: "bench",
            14: "bird",
            15: "cat",
            16: "dog",
            17: "horse",
            18: "sheep",
            19: "cow",
            20: "elephant",
            21: "bear",
            22: "zebra",
            23: "giraffe",
            24: "backpack",
            25: "umbrella",
            26: "handbag",
            27: "tie",
            28: "suitcase",
            29: "frisbee",
            30: "skis",
            31: "snowboard",
            32: "sports ball",
            33: "kite",
            34: "baseball bat",
            35: "baseball glove",
            36: "skateboard",
            37: "surfboard",
            38: "tennis racket",
            39: "bottle",
            40: "wine glass",
            41: "cup",
            42: "fork",
            43: "knife",
            44: "spoon",
            45: "bowl",
            46: "banana",
            47: "apple",
            48: "sandwich",
            49: "orange",
            50: "broccoli",
            51: "carrot",
            52: "hot dog",
            53: "pizza",
            54: "donut",
            55: "cake",
            56: "chair",
            57: "couch",
            58: "potted plant",
            59: "bed",
            60: "dining table",
            61: "toilet",
            62: "tv",
            63: "laptop",
            64: "mouse",
            65: "remote",
            66: "keyboard",
            67: "cell phone",
            68: "microwave",
            69: "oven",
            70: "toaster",
            71: "sink",
            72: "refrigerator",
            73: "book",
            74: "clock",
            75: "vase",
            76: "scissors",
            77: "teddy bear",
            78: "hair drier",
            79: "toothbrush",
        }

    def switch_model(self, model_name: str) -> None:
        if model_name not in _MODELS:
            raise ValueError(f"Unknown model '{model_name}'. Choose from: {list(_MODELS)}")
        with self._lock:
            self._session = None
            self._model_name = model_name
        log.info("model_switched", model=model_name)
